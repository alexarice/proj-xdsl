// RUN: XDSL_ROUNDTRIP

"test.op"() {
  // CHECK: proj = !proj.projection
  proj = !proj.projection,
  // CHECK-SAME: qubit = !proj.qubit
  qubit = !proj.qubit,
  // CHECK-SAME: qubit_x = !proj.qubit<x>
  qubit_x = !proj.qubit<x>,
  // CHECK-SAME: qubit_y = !proj.qubit<y>
  qubit_y = !proj.qubit<y>,
  // CHECK-SAME: qubit_z = !proj.qubit<z>
  qubit_z = !proj.qubit<z>
} : () -> ()
      
