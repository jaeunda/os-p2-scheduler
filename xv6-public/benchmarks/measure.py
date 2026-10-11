#!/usr/bin/env python3
"""Compare weighted CPU-share error with stock round-robin in isolated, instrumented builds."""
from pathlib import Path
import argparse, json, re, statistics, subprocess
from measure_common import BASELINE_SHA, checked_baseline, fixture, build, guest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--output', required=True, type=Path, help='New directory for images, logs and results')
    parser.add_argument('--runs', type=int, default=5)
    args = parser.parse_args()
    if args.runs < 1: parser.error('--runs must be positive')
    baseline = checked_baseline(args.baseline)
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parents[1]
    target = [100/7,200/7,400/7]; results = {}
    for label, original in [('stock_round_robin',baseline),('stride',source)]:
        tree = fixture(original, output/label, 'share')
        code = (source/'benchmarks/share.c').read_text()
        if label == 'stock_round_robin': code = '#define BASELINE\n'+code
        (tree/'share.c').write_text(code)
        (tree/'tick_hook.c').write_text((source/'benchmarks/tick_hook.c').read_text())
        makefile = tree/'Makefile'
        makefile.write_text(makefile.read_text().replace('OBJS = \\', 'OBJS = \\\n\ttick_hook.o \\', 1))
        syscall = tree/'syscall.c'; text = syscall.read_text()
        text = text.replace('static int (*syscalls[])(void) = {',
            'extern int sys_bench_share(void);\nstatic int (*syscalls[])(void) = {\n[30] sys_bench_share,', 1)
        syscall.write_text(text)
        usys = tree/'usys.S'; usys.write_text(usys.read_text()+'\n#define SYS_bench_share 30\nSYSCALL(bench_share)\n')
        trap = tree/'trap.c'; text = trap.read_text()
        text = text.replace('struct spinlock tickslock;', 'extern void bench_tick(void);\nstruct spinlock tickslock;', 1)
        text = text.replace('case T_IRQ0 + IRQ_TIMER:', 'case T_IRQ0 + IRQ_TIMER:\n    bench_tick();', 1)
        if label == 'stride':
            text, changed = re.subn(r'cprintf\("Process %d selected,.*?myproc\(\)->end_ticks\);',
                '/* Measurement build: omit per-tick serial debug output. */', text, flags=re.S)
            assert changed == 1
        trap.write_text(text)
        build(tree, output/(label+'-build.log'))
        runs = []
        for run in range(args.runs):
            transcript = guest(tree, ['share'], output/(label+'-'+str(run+1)+'.log'))
            match = re.search(r'COUNTS (\d+) (\d+) (\d+)', transcript)
            if not match: raise RuntimeError(transcript)
            counts = list(map(int, match.groups())); assert sum(counts) == 300
            shares = [count/3 for count in counts]
            error = max(abs(value-goal) for value,goal in zip(shares,target))
            runs.append(dict(ticks=counts, share_percent=shares, max_error_percentage_points=error))
            print(label, 'run', run+1, counts, 'max error', round(error,4), flush=True)
        results[label] = dict(runs=runs, mean_max_error_percentage_points=
            statistics.mean(run['max_error_percentage_points'] for run in runs))
    results.update(baseline_commit=BASELINE_SHA, tickets=[1000,2000,4000],
        target_share_percent=target, ticks_per_run=300, runs_per_kernel=args.runs,
        virtual_cpus=1, gcc=subprocess.check_output(['gcc-9','-dumpfullversion'], text=True).strip(),
        qemu=subprocess.check_output(['qemu-system-i386','--version'], text=True).splitlines()[0],
        metric='mean across runs of the largest absolute per-worker CPU-share error, in percentage points')
    (output/'results.json').write_text(json.dumps(results, indent=2)+'\n')
if __name__ == '__main__': main()
