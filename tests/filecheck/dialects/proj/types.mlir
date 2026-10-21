// RUN: XDSL_ROUNDTRIP

"test.op"() {
  // CHECK: basis_x = #proj.basis<x>
  basis_x = #proj.basis<x>,
  // CHECK-SAME: basis_y = #proj.basis<y>
  basis_y = #proj.basis<y>,
  // CHECK-SAME: basis_z = #proj.basis<z>
  basis_z = #proj.basis<z>,
  // CHECK-SAME: proj = !proj.projection
  proj = !proj.projection,
  // CHECK-SAME: qubit = !proj.qubit
  qubit = !proj.qubit
} : () -> ()
     
