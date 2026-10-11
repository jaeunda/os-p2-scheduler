// Measurement-only hook: added to temporary kernels by measure.py, never normal builds.
#include "types.h"
#include "defs.h"
#include "param.h"
#include "memlayout.h"
#include "mmu.h"
#include "proc.h"
#include "spinlock.h"
static struct spinlock lock;
static int initialized, active, pids[3], counts[3], total;
void bench_tick(void) {
  int i, done = 0;
  if(!active || !myproc()) return;
  acquire(&lock);
  for(i=0; i<3; i++) if(myproc()->pid == pids[i]) {
    counts[i]++; total++;
    if(total == 300) { active = 0; done = 1; }
    break;
  }
  release(&lock);
  if(done) wakeup(&total);
}
int sys_bench_share(void) {
  int *users, *out, i;
  if(argptr(0, (char**)&users, 3*sizeof(int)) < 0 ||
     argptr(1, (char**)&out, 3*sizeof(int)) < 0) return -1;
  if(!initialized) { initlock(&lock, "benchmark"); initialized = 1; }
  acquire(&lock);
  if(active) { release(&lock); return -1; }
  for(i=0; i<3; i++) { pids[i] = users[i]; counts[i] = 0; }
  total = 0; active = 1;
  while(active) sleep(&total, &lock);
  for(i=0; i<3; i++) out[i] = counts[i];
  release(&lock);
  return 0;
}
