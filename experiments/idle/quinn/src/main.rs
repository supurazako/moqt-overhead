use anyhow::{Context, Result};
use std::sync::Arc;
use std::time::Duration;
use wtransport::Identity;
use wtransport::quinn::{self, TransportConfig, congestion::BbrConfig};

#[tokio::main]
async fn main() -> Result<()> {
    let mut args = std::env::args().skip(1);
    let port: u16 = args.next().context("expected UDP port")?.parse()?;
    let certificate = args.next().context("expected certificate path")?;
    let key = args.next().context("expected private key path")?;
    let identity = Identity::load_pemfiles(certificate, key).await?;
    let mut tls = wtransport::tls::server::build_default_tls_config(identity);
    tls.alpn_protocols.push(b"moqt-22".to_vec());

    let crypto = quinn::crypto::rustls::QuicServerConfig::try_from(tls)?;
    let mut transport = TransportConfig::default();
    transport
        .congestion_controller_factory(Arc::new(BbrConfig::default()))
        .keep_alive_interval(Some(Duration::from_secs(3)))
        .max_idle_timeout(Some(Duration::from_secs(7).try_into()?))
        .max_concurrent_bidi_streams(quinn::VarInt::from_u32(10_000));
    let mut config = quinn::ServerConfig::with_crypto(Arc::new(crypto));
    config.transport_config(Arc::new(transport));

    let endpoint = quinn::Endpoint::server(config, ([0, 0, 0, 0, 0, 0, 0, 0], port).into())?;
    while let Some(incoming) = endpoint.accept().await {
        tokio::spawn(async move {
            if let Ok(connection) = incoming.await {
                connection.closed().await;
            }
        });
    }
    Ok(())
}
