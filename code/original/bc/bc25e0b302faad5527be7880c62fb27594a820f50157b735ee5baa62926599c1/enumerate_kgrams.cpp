// Enumerate DISTINCT strings with specified k-gram multiset and boundary (k-1)-grams.
// Vertices are (k-1)-tuples, edge multiplicities are indistinguishable.
// Branch only over distinct next vertices. Reachability pruning changes no outputs.
#include <algorithm>
#include <cstdint>
#include <fstream>
#include <iostream>
#include <map>
#include <queue>
#include <stdexcept>
#include <vector>
using namespace std;
struct Enumerator {
 int n,k,V,remaining,goal; uint64_t emitted=0,nodes=0,pruned=0,limit;
 vector<vector<int>> labels,adj,neighbors; vector<int> out,path; vector<unsigned char> raw;
 ofstream dest;
 bool connected(int start) {
  vector<bool> seen(V,false); vector<int> q{start}; seen[start]=true;
  for(size_t p=0;p<q.size();++p) for(int v:neighbors[q[p]])
   if(adj[q[p]][v]>0&&!seen[v]) {seen[v]=true;q.push_back(v);}
  for(int u=0;u<V;++u) if(out[u]>0&&!seen[u])return false;
  return true;
 }
 void dfs(int u) {
  ++nodes;
  if(remaining==0) {
   if(u!=goal)throw runtime_error("wrong endpoint");
   for(int j=0;j<k-1;++j)raw[j]=(unsigned char)labels[path[0]][j];
   for(size_t i=1;i<path.size();++i)raw[k-2+i]=(unsigned char)labels[path[i]].back();
   dest.write(reinterpret_cast<char*>(raw.data()),n); if(!dest)throw runtime_error("output write failed");
   if(++emitted>limit)throw runtime_error("enumeration exceeded expected count");
   return;
  }
  int choices=0;for(int v:neighbors[u])if(adj[u][v])++choices;
  for(int v:neighbors[u])if(adj[u][v]) {
   --adj[u][v];--out[u];--remaining;path.push_back(v);
   if(choices<=1||connected(v))dfs(v);else ++pruned;
   path.pop_back();++remaining;++out[u];++adj[u][v];
  }
 }
 void run(const char* input,const char* output,uint64_t expected) {
  limit=expected;ifstream f(input); if(!(f>>n>>k)||n<k||k<2)throw runtime_error("bad header");
  vector<int>s(n);for(int&i:s)if(!(f>>i)||i<0||i>255)throw runtime_error("bad glyph");
  map<vector<int>,int> ids;vector<int> vs;
  for(int i=0;i<=n-k+1;++i){vector<int> v(s.begin()+i,s.begin()+i+k-1);
   if(!ids.count(v)){ids[v]=labels.size();labels.push_back(v);}vs.push_back(ids.at(v));}
  V=labels.size();adj.assign(V,vector<int>(V,0));neighbors.assign(V,{});out.assign(V,0);
  for(size_t i=1;i<vs.size();++i){++adj[vs[i-1]][vs[i]];++out[vs[i-1]];}
  for(int u=0;u<V;++u)for(int v=0;v<V;++v)if(adj[u][v])neighbors[u].push_back(v);
  remaining=n-k+1;goal=vs.back();path={vs.front()};raw.resize(n);dest.open(output,ios::binary);
  if(!dest)throw runtime_error("cannot create output");dfs(vs.front());dest.close();
  if(emitted!=expected)throw runtime_error("enumeration incomplete");
  cout<<"{\"strings\":"<<emitted<<",\"recursion_nodes\":"<<nodes<<",\"reachability_prunes\":"<<pruned<<"}\n";
 }
};
int main(int argc,char**argv){try{if(argc!=4)throw runtime_error("usage: input output expected_count");Enumerator e;e.run(argv[1],argv[2],stoull(argv[3]));return 0;}catch(const exception&e){cerr<<e.what()<<"\n";return 1;}}
