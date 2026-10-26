// RUN: XDSL_ROUNDTRIP

"test.op"() {
  // CHECK: zero = !angle.type
  zero = !angle.type
} : () -> ()

// CHECK: %zero = angle.zero
%zero = angle.zero

// CHECK: %pi = angle.pi
%pi = angle.pi

// CHECK: %sum = angle.add %zero, %pi
%sum = angle.add %zero, %pi

// CHECK: %scaled = angle.scalar_mult 2.000000e+00, %pi
%scaled = angle.scalar_mult 2.0, %pi
