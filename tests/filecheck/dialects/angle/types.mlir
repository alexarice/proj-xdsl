// RUN: XDSL_ROUNDTRIP

"test.op"() {
  // CHECK: angle = !angle.type
  angle = !angle.type
} : () -> ()
      
