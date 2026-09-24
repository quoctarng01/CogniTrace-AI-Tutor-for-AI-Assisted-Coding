from pathlib import Path
migs = sorted(Path('migrations').glob('*.sql'))
for sql in migs:
    content = sql.read_text(encoding='utf-8')
    assert ('CREATE TABLE' in content
            or 'CREATE POLICY' in content
            or 'CREATE INDEX' in content
            or 'CREATE FUNCTION' in content
            or content.strip().startswith('--')), f'{sql.name} has no recognisable DDL/DML'
print(f'OK: {len(migs)} migration file(s) scanned')
for m in migs:
    print(f'  - {m.name}')
