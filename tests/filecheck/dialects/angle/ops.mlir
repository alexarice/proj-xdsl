// RUN: XDSL_ROUNDTRIP

"test.op"() {
  // CHECK: zero = !angle.type
  zero = !angle.type
} : () -> ()

// CHECK: %zero = angle.zero
%zero = angle.zero

// CHECK: %pi = angle.pi
%pi = angle.pi
