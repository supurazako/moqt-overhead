"""Generate small, explicit measurement adapters from pinned upstream sources."""
from pathlib import Path
import difflib

ROOT=Path(__file__).resolve().parents[2]
patches=ROOT/'.scratch/endpoint-patches'
patches.mkdir(exist_ok=True)


def save(name, original, updated):
    (patches/name).write_text(updated)
    (ROOT/'experiments/endpoints'/f'{name}.patch').write_text(''.join(difflib.unified_diff(
        original.splitlines(True),updated.splitlines(True),fromfile='upstream/'+name,tofile='measured/'+name)))

for name in ('moq-test.c','moq-sub.c'):
    original=(ROOT/'.scratch/endpoint-sources'/name).read_text()
    updated=original.replace('IMQUIC_CONFIG_TLS_NO_VERIFY, TRUE,','IMQUIC_CONFIG_TLS_NO_VERIFY, FALSE,')
    if name=='moq-test.c':
        marker='static void imquic_demo_publish_namespace_accepted('
    else:
        marker='static void imquic_demo_subscribe_accepted('
    start=updated.index(marker); brace=updated.index('{',start)
    updated=updated[:brace+1]+'\n\tIMQUIC_PRINT("BENCH_READY\\n"); fflush(stdout);'+updated[brace+1:]
    if name=='moq-sub.c':
        marker='static void imquic_demo_incoming_object(imquic_connection *conn, imquic_moq_object *object) {'
        extra='''
    static unsigned bench_count = 0, bench_errors = 0;
    if(object->payload_len > 0) {
        if(object->group_id != 0 || object->object_id != bench_count || object->payload_len != 64)
            bench_errors++;
        for(size_t i=0; i<object->payload_len; ++i)
            if(object->payload[i] != 't') { bench_errors++; break; }
        bench_count++;
        if(bench_count == 50) {
            IMQUIC_PRINT("BENCH_RECEIVED %u %u\\n", bench_count, bench_errors); fflush(stdout);
        }
    }
'''
        updated=updated.replace(marker,marker+extra)
    save(name,original,updated)

base=ROOT/'.scratch/endpoint-moqtail/apps/client/src'
for name in ('publisher.rs','subscriber.rs'):
    original=(base/name).read_text();updated=original
    if name=='publisher.rs':
        updated=updated.replace('info!("Namespace published successfully");','println!("BENCH_READY");\n      info!("Namespace published successfully");')
        start=updated.index('fn generate_payload(size: usize) -> Vec<u8> {')
        end=updated.index('\n#[cfg(test)]',start)
        updated=updated[:start]+"fn generate_payload(size: usize) -> Vec<u8> { vec![b't'; size] }\n"+updated[end:]
    else:
        marker='    Ok(ControlMessage::SubscribeOk(m)) => {'
        assert marker in updated
        updated=updated.replace(marker,marker+'\n      println!("BENCH_READY");')
        marker='                  let sequence_ok = matches!(status, "OK" | "FILL");'
        assert marker in updated
        updated=updated.replace(marker,'''                  if let Some(payload) = &obj.payload {
                    if payload.len() != 64 || payload.iter().any(|byte| *byte != b't') {
                      stats.record_parse_error();
                    }
                  }
                  if stats.total_received == 50 {
                    println!("BENCH_RECEIVED {} {}", stats.total_received,
                      stats.parse_errors + stats.sequence_gaps + stats.duplicates);
                  }
'''+marker)
    save(name,original,updated)
    (base/name).write_text(updated)
