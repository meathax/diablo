#include <stdio.h>
#include <stdint.h>
#include <time.h>
__attribute__((noinline)) int original(int d,int p,int l){int r=d%p;if(d<0)return r+(r<0?p:0);return (d/p)*l+r;}
__attribute__((noinline)) int candidate(int d,int p,int l){if(d>=0&&p==l)return d;int r=d%p;if(d<0)return r+(r<0?p:0);return (d/p)*l+r;}
static double now(void){struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec*1e-9;}
static int addresses[1024];
int main(void){int pitches[][2]={{640,640},{672,640},{640,64},{32,32}};for(unsigned k=0;k<4;k++)for(int d=-4096;d<640*600;d++)if(original(d,pitches[k][0],pitches[k][1])!=candidate(d,pitches[k][0],pitches[k][1]))return 2;for(int i=0;i<1024;i++)addresses[i]=(i*293)%307200;volatile uint32_t sum=0;for(int pass=0;pass<4;pass++){double a=now();for(int i=0;i<1000000;i++)sum+=original(addresses[i&1023],640,640);double b=now();for(int i=0;i<1000000;i++)sum+=candidate(addresses[i&1023],640,640);double c=now();printf("pass=%d original_ms=%.3f candidate_ms=%.3f\n",pass,(b-a)*1000,(c-b)*1000);}printf("equivalence=pass checksum=%u\n",sum);}
