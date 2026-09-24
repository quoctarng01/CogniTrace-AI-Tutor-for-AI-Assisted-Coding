import os, re

roots = ['app', 'components', 'hooks', 'lib']
missing = []
for root in roots:
    if not os.path.isdir(root):
        continue
    for dp, dn, fn in os.walk(root):
        for f in fn:
            if not (f.endswith('.tsx') or f.endswith('.ts')):
                continue
            p = os.path.join(dp, f)
            with open(p, 'r', encoding='utf-8') as fh:
                src = fh.read()
            # Heuristic: docstring or file-level JSDoc block comment at top
            if not re.search(r'^\s*(/\*\*|//!)', src, re.MULTILINE):
                missing.append(p)
for p in missing:
    print(p)
print(f'TOTAL_MISSING={len(missing)}')
