package chromaapex
import("testing";"math";"math/rand";"sort")
func TestSorted(t *testing.T){
  r:=rand.New(rand.NewSource(1234))
  for _,n:=range []int{0,1,2,17,120,1024,10000}{
    xs:=make([]float64,n);for i:=range xs {xs[i]=float64(r.Intn(99)-50)}
    if n>3{xs[0]=math.NaN();xs[2]=math.Inf(-1)}
    ix,err:=OrderFloat64(xs);if err!=nil{t.Fatal(err)}
    ref:=make([]int,n);for i:=range ref{ref[i]=i}
    sort.SliceStable(ref,func(i,j int) bool{a,b:=xs[ref[i]],xs[ref[j]];if math.IsNaN(a){return false};if math.IsNaN(b){return true};return a<b})
    for i,x:=range ix {if int(x)!=ref[i]{t.Fatalf("n=%d i=%d got=%d expected=%d",n,i,x,ref[i])}}
  }
}
