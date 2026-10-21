// RUN: XDSL_ROUNDTRIP

"test.op"() {
  // CHECK: proj = !proj.projection
  proj = !proj.projection,
  // CHECK-SAME: qubit = !proj.qubit
  qubit = !proj.qubit
} : () -> ()
    
