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

// CHECK: %scaled = angle.scalar_mult %scalar, %pi
%scalar = arith.constant 2.0 : f64
%scaled = angle.scalar_mult %scalar, %pi
