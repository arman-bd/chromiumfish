//! canvas-bridge-server — accepts ChromiumFish render-bridge sessions,
//! replays canvas2d / WebGL / font ops against the host's native graphics
//! stack, and ships the resulting pixels / metrics back.

use std::net::SocketAddr;
use std::path::PathBuf;
use std::sync::Arc;

use anyhow::{Context, Result};
use clap::Parser;
use futures_util::{SinkExt, StreamExt};
use tokio::net::TcpListener;
use tokio_tungstenite::tungstenite::Message;
use tracing::{error, info, warn};

mod auth;
mod canvas2d;
mod fonts;
mod session;
mod text;
mod webgl;
#[cfg(feature = "webgl")]
mod webgl_real;

use crate::auth::AuthConfig;

#[derive(Parser, Debug)]
#[command(
    name = "canvas-bridge-server",
    version,
    about = "Remote canvas / WebGL / font render server for ChromiumFish"
)]
struct Args {
    /// Listen address (host:port).
    #[arg(long, default_value = "127.0.0.1:8443")]
    listen: SocketAddr,

    /// Basic-auth credential — "user:secret". Clients must present the
    /// same value via `Authorization: Basic <base64(user:secret)>` on
    /// the WebSocket upgrade. Required.
    #[arg(long, env = "CANVAS_BRIDGE_AUTH")]
    auth: String,

    /// TLS certificate chain (PEM). If both --cert and --key are given,
    /// the server listens on `wss://`; otherwise it listens on `ws://`
    /// (plaintext — for local testing only).
    #[arg(long)]
    cert: Option<PathBuf>,

    #[arg(long)]
    key: Option<PathBuf>,
}

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info,canvas_bridge_server=debug".into()),
        )
        .init();

    let args = Args::parse();

    // Tokio runtime: bump the blocking-thread ceiling so the renderer
    // pool can grow past Tokio's 512 default. Each session pins one
    // blocking thread for the per-session render loop; with the
    // default cap, 1024 concurrent sessions queue. 2048 gives ~4×
    // headroom on M1-class hardware before paging.
    let rt = tokio::runtime::Builder::new_multi_thread()
        .enable_all()
        .max_blocking_threads(2048)
        .build()?;
    rt.block_on(run(args))
}

async fn run(args: Args) -> Result<()> {
    let auth_cfg = Arc::new(AuthConfig::parse(&args.auth)?);

    // TLS is intentionally not built into the default profile (no
    // rustls / ring dependency). Use behind an SSH tunnel or
    // localhost-only on the same host as the renderer.
    if args.cert.is_some() || args.key.is_some() {
        warn!("--cert / --key flags are accepted for compat but TLS is \
               not compiled in. Run plaintext via SSH tunnel.");
    }

    let listener = TcpListener::bind(args.listen)
        .await
        .with_context(|| format!("bind {}", args.listen))?;
    info!(addr = %args.listen, "canvas-bridge-server listening");

    loop {
        let (tcp, peer) = match listener.accept().await {
            Ok(v) => v,
            Err(e) => {
                error!(err = %e, "accept failed");
                continue;
            }
        };
        let auth = auth_cfg.clone();
        tokio::spawn(async move {
            if let Err(e) = serve_one(tcp, peer, auth).await {
                warn!(peer = %peer, err = %e, "session ended with error");
            }
        });
    }
}

async fn serve_one(
    tcp: tokio::net::TcpStream,
    peer: SocketAddr,
    auth: Arc<AuthConfig>,
) -> Result<()> {
    // Custom WebSocket accept so we can check the Authorization header
    // before upgrading.
    let ws = tokio_tungstenite::accept_hdr_async(
        tcp,
        |req: &tokio_tungstenite::tungstenite::handshake::server::Request,
         resp: tokio_tungstenite::tungstenite::handshake::server::Response| {
            auth.check_request(req).map_err(|e| {
                tracing::warn!(peer = %peer, err = %e, "auth rejected");
                tokio_tungstenite::tungstenite::handshake::server::ErrorResponse::new(Some(
                    format!("auth: {e}"),
                ))
            })?;
            Ok(resp)
        },
    )
    .await
    .context("ws handshake")?;

    info!(peer = %peer, "session opened");
    let (mut tx, mut rx) = ws.split();

    // Pipeline:
    //   reader (async) → op_tx → render (blocking) → reply_tx → writer (async)
    //
    // The reader can keep pulling frames from the socket while the
    // renderer is CPU-busy on previous ops, and the writer can be
    // flushing earlier replies in parallel. All three legs run
    // concurrently on tokio.
    let (op_tx, op_rx) =
        tokio::sync::mpsc::channel::<Vec<u8>>(1024);
    let (reply_tx, mut reply_rx) =
        tokio::sync::mpsc::channel::<canvas_bridge_proto::ServerMsg>(256);

    let render_handle = tokio::task::spawn_blocking(move || {
        let mut sess = session::Session::new();
        let mut op_rx = op_rx;
        while let Some(buf) = op_rx.blocking_recv() {
            for reply in sess.handle(&buf) {
                if reply_tx.blocking_send(reply).is_err() {
                    return;
                }
            }
        }
    });

    let writer_handle: tokio::task::JoinHandle<Result<()>> = tokio::spawn(async move {
        while let Some(reply) = reply_rx.recv().await {
            let bytes = canvas_bridge_proto::encode(&reply)?;
            tx.send(Message::Binary(bytes)).await.context("ws send")?;
        }
        Ok(())
    });

    let reader_result: Result<()> = async {
        while let Some(msg) = rx.next().await {
            let msg = msg.context("ws recv")?;
            match msg {
                Message::Binary(buf) => {
                    if op_tx.send(buf).await.is_err() {
                        break; // render side closed
                    }
                }
                Message::Close(_) => break,
                Message::Ping(_)
                | Message::Pong(_)
                | Message::Text(_)
                | Message::Frame(_) => {}
            }
        }
        Ok(())
    }
    .await;
    drop(op_tx); // signal renderer to drain & exit

    // Wait for renderer + writer to finish flushing.
    let _ = render_handle.await;
    let _ = writer_handle.await;
    info!(peer = %peer, "session closed");
    reader_result
}
