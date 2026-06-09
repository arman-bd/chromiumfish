//! HTTP Basic auth gate on the WebSocket upgrade.

use anyhow::{anyhow, bail, Context, Result};
use base64::Engine;

pub struct AuthConfig {
    user: String,
    secret: String,
}

impl AuthConfig {
    pub fn parse(spec: &str) -> Result<Self> {
        let (user, secret) = spec
            .split_once(':')
            .ok_or_else(|| anyhow!("--auth must be 'user:secret'"))?;
        if user.is_empty() || secret.is_empty() {
            bail!("--auth user and secret must be non-empty");
        }
        Ok(Self { user: user.into(), secret: secret.into() })
    }

    pub fn check_request(
        &self,
        req: &tokio_tungstenite::tungstenite::handshake::server::Request,
    ) -> Result<()> {
        let auth = req
            .headers()
            .get("Authorization")
            .ok_or_else(|| anyhow!("missing Authorization header"))?;
        let auth = auth.to_str().context("Authorization not ASCII")?;
        let value = auth.strip_prefix("Basic ").ok_or_else(|| {
            anyhow!("only Basic auth supported; got {}", auth.split_whitespace().next().unwrap_or(""))
        })?;
        let decoded = base64::engine::general_purpose::STANDARD
            .decode(value.trim())
            .context("Authorization base64 decode")?;
        let decoded = std::str::from_utf8(&decoded).context("Authorization utf8")?;
        let (user, secret) = decoded
            .split_once(':')
            .ok_or_else(|| anyhow!("malformed Authorization payload"))?;
        if constant_time_eq(user.as_bytes(), self.user.as_bytes())
            && constant_time_eq(secret.as_bytes(), self.secret.as_bytes())
        {
            Ok(())
        } else {
            bail!("invalid credentials")
        }
    }
}

fn constant_time_eq(a: &[u8], b: &[u8]) -> bool {
    if a.len() != b.len() {
        return false;
    }
    let mut diff: u8 = 0;
    for (x, y) in a.iter().zip(b.iter()) {
        diff |= x ^ y;
    }
    diff == 0
}
