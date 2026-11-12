#!/usr/bin/env python3
"""Generate diagnostic module-order references, never an init load override.

The stock vendor_boot owns first-stage loading on this recovery_ab device.
A regular modules.load.recovery in the ramdisk enables strict init loading and
has not been validated with our flattened dependency metadata. TWRP's own
second-stage loader generates modules.load.twrp independently.
"""
import os
import sys

def read_dep(path):
    deps = {}
    if not os.path.exists(path):
        return deps
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or ':' not in line:
                continue
            mod, rest = line.split(':', 1)
            deps[os.path.basename(mod.strip())] = [
                os.path.basename(x.strip()) for x in rest.split() if x.strip()]
    return deps

def topo_order(deps, present):
    order, state = [], {}

    def visit(name, stack):
        st = state.get(name)
        if st == 2 or name not in present:
            return
        if st == 1:            # cycle: keep whatever order we already have
            return
        state[name] = 1
        for dep in deps.get(name, []):
            visit(dep, stack + [name])
        state[name] = 2
        order.append(name)

    for name in sorted(present):
        visit(name, [])
    return order

def main(root):
    touched = 0
    for ver in sorted(os.listdir(root)):
        d = os.path.join(root, ver)
        if not os.path.isdir(d):
            continue
        present = sorted(f for f in os.listdir(d) if f.endswith('.ko'))
        deps = read_dep(os.path.join(d, 'modules.dep'))
        order = topo_order(deps, set(present))
        # Anything the dep file did not mention still has to be listed.
        order += [m for m in present if m not in order]
        out = os.path.join(d, 'modules.load.reference')
        with open(out, 'w') as f:
            f.write('\n'.join(order) + '\n')
        missing = [m for m in order if not os.path.exists(os.path.join(d, m))]
        print(f"{ver}: {len(order)} modules -> {out}"
              f"{'  MISSING: ' + ','.join(missing) if missing else ''}")
        touched += 1
    return 0 if touched else 1

if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else
                  'recovery/root/lib/modules'))
