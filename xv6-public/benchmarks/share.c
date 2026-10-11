// Three CPU-bound children; the parent sleeps while a test-only kernel hook counts ticks.
#include "types.h"
#include "stat.h"
#include "user.h"
int bench_share(int*, int*);
static void fail(void) { printf(2, "FAIL setup\n"); exit(); }
int main(void) {
  int ready[2], release[3][2], pids[3], counts[3], i, j;
  char byte = 'R';
  if(pipe(ready) < 0) fail();
  for(i=0; i<3; i++) if(pipe(release[i]) < 0) fail();
  for(i=0; i<3; i++) {
    pids[i] = fork();
    if(pids[i] < 0) fail();
    if(!pids[i]) {
      volatile uint work = 0;
      close(ready[0]);
      for(j=0; j<3; j++) { close(release[j][1]); if(j!=i) close(release[j][0]); }
#ifndef BASELINE
      if(settickets(1000 << i, -1) < 0) fail();
#endif
      if(write(ready[1], &byte, 1)!=1) fail();
      close(ready[1]);
      if(read(release[i][0], &byte, 1)!=1) fail();
      close(release[i][0]);
      for(;;) work++;
    }
  }
  close(ready[1]);
  for(i=0; i<3; i++) if(read(ready[0], &byte, 1)!=1) fail();
  close(ready[0]);
  for(i=0; i<3; i++) {
    close(release[i][0]);
    if(write(release[i][1], &byte, 1)!=1) fail();
    close(release[i][1]);
  }
  if(bench_share(pids, counts) < 0) fail();
  for(i=0; i<3; i++) kill(pids[i]);
  for(i=0; i<3; i++) wait();
  printf(1, "COUNTS %d %d %d\n", counts[0], counts[1], counts[2]);
  exit();
}
