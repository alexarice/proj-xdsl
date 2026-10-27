# Type System Design for Projective Quantum Language

## Overview

This document specifies the type system for a quantum programming language based on projective predicates. The type system uses a borrowing-based approach to statically ensure that all projections commute, enabling safe composition of quantum predicates.

**Design constraint**: No higher-order functions. All functions are first-level definitions only.

## Core Types

```
qubit         - Qubit
qubit<B>      - Qubit borrowed in basis B, where B ∈ {X, Y, Z}
proj          - Projection (opaque type)
bool          - Classical boolean (subtype of proj)
angle         - Classical angle (for Phase gates)
```

### Type Semantics

- **`qubit` (unborrowed qubit)**: a qubit that is not currently borrowed. Can be used to create projections in any basis, but projections borrowing this qubit cannot escape the scope. **Function parameters of type `qubit` are considered borrowed** - they cannot be returned from the function.

- **`qubit<B>` (borrowed qubit)**: a qubit that is borrowed in a specific basis. Only projections in that basis (or compatible bases) can be created.

- **`proj` (projection)**: a projection value that may borrow one or more qubits. Projections are first-class, copyable values (but cannot be passed to higher-order functions).

- **`bool` (boolean)**: Classical boolean value, used for measurement results and classical control flow. **`bool` is a subtype of `proj`** - booleans can be used wherever projections are expected (e.g., in `if` statements, with connectives). Can be freely returned from functions (no borrowing).

- **`angle` (angle)**: Classical angle value, used for Phase gate parameters. Can be freely returned from functions (no borrowing). Supports arithmetic operations and constants.

- **Basis compatibility**:
  - Same basis: Compatible (multiple Z-borrows allowed)
  - Different basis: Incompatible (X and Z on same qubit = error)
  - Total borrow: Control flow disagreement creates a "total borrow" that prevents any new borrows

- **Qubit ownership**: Functions can return qubits, but **only qubits allocated within the function scope**. Function parameters (even `qubit`) cannot be returned.

## Surface Syntax

### Type Annotations

```rust
fn f(q: qubit<Z>, p: proj) -> proj { ... }      // qubit borrowed in Z basis
fn g(q: qubit, p: proj) -> proj { ... }         // qubit unborrowed
fn h(p: proj) -> proj { ... }                   // Projection parameter (always reborrowed)
```

**Notation**: `qubit<B>` uses angle bracket syntax for basis annotations. Only one basis annotation is allowed per qubit parameter.

### Expression Syntax

```rust
// Projection creation (both ASCII and Unicode notation accepted)
q == |0>         // Qubit q projected to |0> state (Z basis)
q == |0⟩         // Same as above (Unicode notation)
q == |+>         // Qubit q projected to |+> state (X basis)
q == |L>         // Qubit q projected to |L> state (Y basis)

// Connectives (work on proj or bool, since bool <: proj)
p1 && p2         // Conjunction (and)
p1 || p2         // Disjunction (or)
p1 ^ p2          // Exclusive-or (xor)
!p               // Negation (not)
b1 && b2         // Boolean conjunction (bool <: proj)

// Conditional (accepts proj or bool, since bool <: proj)
if p {
    phase(PI)    // Phase gate (primitive operation)
}
if b {           // Boolean can be used directly
    phase(PI)
}

// Measurement
let b: bool = measure(p)    // Returns bool
if b {                      // bool can be used in if (subtype of proj)
    phase(PI)
}

// Allocation
let q = alloc |0>

// Angle arithmetic
let a1: angle = PI + PI/2;           // Addition
let a2: angle = PI - PI/4;           // Subtraction
let a3: angle = 2.0 * PI;            // Scalar multiplication
let a4: angle = PI / 3.0;            // Scalar division
let a5: angle = 0;                   // Zero constant
```

### Angle Constants

```rust
PI      // π (also accepts unicode: π)
0       // Zero angle
```

### Function Definitions

```rust
// Basic function
fn phase_oracle(q1: qubit<Z>, q2: qubit<Z>, p: proj) -> proj {
    if q1 == |0> && q2 == |1> && p {
        phase(PI)
    }
}

// Function with local variables
fn example(q: qubit) {
    let proj = q == |0>;
    if proj {
        phase(PI)
    }
}

// Function returning projection (only from reborrowed params)
fn identity(p: proj) -> proj {
    p
}
```

## Borrow Semantics

### Core Rules

1. **Projection Reborrowing**: Output projections reborrow from all input projection parameters. If a function takes `p: proj` and returns `proj`, the returned projection inherits all borrows from `p`.

2. **Local Qubit Borrows**: Functions can create projections on local qubits or bare `qubit` parameters, but these projections **cannot be returned**. Only projections that borrow from input `proj` parameters may escape.

3. **Basis Compatibility**: At any program point, a qubit cannot be borrowed in incompatible bases simultaneously. Same-basis borrows are compatible.

4. **Total Borrow**: When control flow paths disagree on which basis a qubit is borrowed in, the qubit receives a "total borrow" that prevents any new borrows until the projection is released.

5. **Borrow Release**: Borrows are released when the projection value goes out of scope (NLL-style semantics).

### Borrow Signature

Every function has an inferred borrow signature:

```
fn f(q: qubit<Z>, p: proj) -> proj
```

**Semantics**:
- `q: qubit<Z>` - Caller must provide qubit available in Z basis
- `p: proj` - Projection parameter (always reborrowed)
- Return `proj` - Reborrow from input `p` plus any new borrows created in function body

**Inference Rules**:
- Walk function body to determine which qubits are borrowed and in which bases
- For control flow: union of bases from all paths
- Multiple bases for same qubit → total borrow
- Returned projections can only borrow from input `proj` parameters

## Validation Rules

### Function Body Validation

1. **Qubit parameter usage**: If `q: qubit<B>`, all projections on `q` must be in basis `bool` (or compatible)

2. **Bare qubit usage**: If `q: qubit`, projections can be created in any basis, but cannot be returned

3. **Projection reborrowing**: Returned projections must only borrow from input `proj` parameters (not from local qubits or bare `qubit` params)

4. **Qubit return validation**: Functions can return `qubit`, but **only qubits allocated within the function scope**. Function parameters of type `qubit` cannot be returned.

5. **Classical return validation**: Functions can freely return `bool` and `angle` (classical types have no borrowing semantics).

6. **Borrow compatibility**: No qubit can have incompatible active borrows at any program point

### Call-Site Validation

1. **Qubit availability**: Actual qubit arguments must be available in the required basis

2. **Projection availability**: Actual projection arguments must not be currently borrowed

3. **Borrow conflict detection**: If caller has incompatible borrows active, call is invalid

## Examples

### Valid Programs

```rust
// Example 1: Compatible borrows
fn phase_oracle(q1: qubit<Z>, q2: qubit<Z>, p: proj) -> proj {
    if q1 == |0> && q2 == |1> && p {
        phase(PI)
    }
}

// Call site (valid - all Z basis)
let q1 = alloc |0>;
let q2 = alloc |0>;
let p = q1 == |0>;
phase_oracle(q1, q2, p);  // ✅ OK
```

```rust
// Example 2: Projection reborrowing
fn identity(p: proj) -> proj {
    p  // ✅ OK - only reborrow from input proj
}

fn extend(q: qubit<Z>, p: proj) -> proj {
    p && (q == |0>  // ✅ OK - reborrow p + new Z borrow on q
}
```

```rust
// Example 3: Bare qubit (not returned)
fn use_local(q: qubit) {
    let proj = q == |0>;  // ✅ OK - Z basis projection
    if proj {
        phase(PI)
    }
    // proj released at end of scope
}
```

```rust
// Example 4: Multiple compatible borrows
fn multi_borrow(q1: qubit<Z>, q2: qubit<Z>) {
    let p1 = q1 == |0>;  // Z borrow on q1
    let p2 = q2 == |1>;  // Z borrow on q2
    if p1 && p2 {
        phase(PI)
    }
}
```

```rust
// Example 5: Returning locally-allocated qubit
fn make_qubit() -> qubit {
    let q = alloc |0>;
    q  // ✅ OK - q was allocated in this function
}
```

```rust
// Example 6: Using returned qubit
fn use_returned() {
    let q = make_qubit();
    let proj = q == |0>;
    if proj {
        phase(PI)
    }
}
```

```rust
// Example 7: Returning classical data
fn measure_qubit(q: qubit) -> bool {
    let proj = q == |0>;
    measure(proj)  // ✅ OK - bool can be freely returned
}
```

```rust
// Example 8: Returning angle
fn get_phase() -> angle {
    PI  // ✅ OK - angle can be freely returned
}
```

```rust
// Example 9: Angle arithmetic
fn custom_phase(q: qubit, theta: angle) {
    let adjusted = theta + PI/2;
    phase(adjusted)  // ✅ OK - angle addition
}

fn half_phase(q: qubit) {
    phase(PI / 2.0)  // ✅ OK - angle division
}

fn double_phase(q: qubit) {
    phase(2.0 * PI)  // ✅ OK - scalar multiplication
}
```

```rust
// Example 10: Boolean as projection (bool <: proj)
fn use_measurement(q: qubit) {
    let b: bool = measure(q == |0>);
    if b {              // ✅ OK - bool can be used in if (subtype of proj)
        phase(PI)
    }
}

fn boolean_ops(q1: qubit, q2: qubit) {
    let b1: bool = measure(q1 == |0>);
    let b2: bool = measure(q2 == |0>);
    if b1 && b2 {       // ✅ OK - boolean conjunction
        phase(PI)
    }
}
```

### Invalid Programs

```rust
// Example 1: Incompatible bases
fn bad(q: qubit<Z>, p: proj) -> proj {
    if q == |+> && p {  // ❌ ERROR - q is qubit<Z> but X basis used
        phase(PI)
    }
}
```

```rust
// Example 2: Returning local qubit borrow
fn make_proj(q: qubit) -> proj {
    q == |0>  // ❌ ERROR - cannot return projection borrowing local q
}
```

```rust
// Example 3: Call-site conflict
fn f(q: qubit<Z>, p: proj) -> proj { ... }

let q = alloc |0>;
let p1 = q == |0>;      // q borrowed in Z
let p2 = q == |+>;      // ❌ ERROR - q already borrowed in Z, can't borrow in X
f(q, p1);
```

```rust
// Example 4: Total borrow from control flow
fn conditional(c: bool, q: qubit) -> proj {
    if c {
        q == |0>    // Z basis
    } else {
        q == |+>    // X basis
    }
    // ❌ ERROR - total borrow on q (Z or X), caller cannot use q
}
```

```rust
// Example 5: Incompatible borrows on same qubit
fn incompatible(q: qubit<Z>, p: proj) -> proj {
    let p2 = q == |+>;  // ❌ ERROR - q is qubit<Z>, can't borrow in X
    p && p2
}
```

```rust
// Example 8: Returning parameter qubit
fn return_param(q: qubit) -> qubit {
    q  // ❌ ERROR - cannot return qubit parameter (even if bare qubit)
}
```

```rust
// Example 9: Cannot return borrowed qubit
fn return_borrowed(q1: qubit, q2: qubit) -> qubit {
    let q3 = alloc |0>;
    q1  // ❌ ERROR - q1 is a parameter, cannot return
}
```

## Borrow Analysis Algorithm

### Phase 1: Signature Inference

For each function:
1. Walk function body
2. Track active borrows per qubit (SSA value → set of bases)
3. At control flow merge points: union of bases from all paths
4. Multiple bases for same qubit → mark as total borrow
5. Determine which borrows escape in return value

### Phase 2: Body Validation

For each function:
1. Verify qubit parameter usage matches signature
2. Verify returned projections only borrow from input `proj` parameters
3. Verify returned qubits are locally allocated (not parameters)
4. Verify no incompatible borrows at any program point
5. Verify total borrows don't have new borrows created

### Phase 3: Call-Site Validation

For each call:
1. Check actual qubit params have required basis availability
2. Check actual projection params are not currently borrowed
3. Check no conflicts between new borrows and existing borrows

## Function Kinds

Functions are classified into three kinds based on their effect on quantum state:

### `pure fn` - Purely Classical Computation
- **Semantics**: No quantum operations; classical computation only
- **Allowed**: Classical control, arithmetic, boolean logic
- **Disallowed**: Qubit allocation, phase gates, projections, measurement
- **Return types**: Any type (typically `bool`, `angle`), or void `()`
- **Use case**: Classical post-processing, computing classical functions from measurement results

```rust
pure fn classical_post_process(m1: bool, m2: bool) -> bool {
    return m1 && m2
}

pure fn add_angles(a1: angle, a2: angle) -> angle {
    return a1 + a2
}
```

### `unitary fn` - Unitary Evolution
- **Semantics**: Quantum operations without measurement or allocation
- **Allowed**: Projections, phase gates, unitary transforms on borrowed qubits
- **Disallowed**: Qubit allocation (`alloc`), measurement (`measure`)
- **Return types**: Any type, or void `()`
- **Use case**: Gates (void), oracles (classical output via phase kickback), basis changes

```rust
// Gate - transforms borrowed qubits, no return
unitary fn hadamard(q: qubit<Z>) {
    // q is borrowed, transformed in place
}

// Oracle - unitary with classical output (no measurement)
unitary fn phase_oracle(q: qubit<Z>) -> bool {
    phase(PI)
    return true  // computed without measurement
}
```

### `mixed fn` - General Quantum Channel
- **Semantics**: Arbitrary CPTP map; full quantum operations with measurement
- **Allowed**: All operations including mid-circuit measurement and allocation
- **Return types**: Any type, or void `()`
- **Use case**: Full algorithms, error correction, measurement-based protocols

```rust
mixed fn teleport(src: qubit, dst: qubit) -> qubit {
    // Bell measurement
    let m1 = measure(src == |0>)
    let m2 = measure(src == |+>)
    // Classical correction
    if m1 { phase(PI) }
    if m2 { ... }
    return dst
}

mixed fn measure_and_reset(q: qubit) -> bool {
    return measure(q == |0>)
}
```

### Kind Hierarchy

```
pure ⊆ unitary ⊆ mixed
```

- `pure` functions are a subset of `unitary` (classical ops are trivially unitary)
- `unitary` functions are a subset of `mixed` (unitary ops are a special case of channels)
- A `pure fn` can be called where `unitary fn` or `mixed fn` is expected
- A `unitary fn` can be called where `mixed fn` is expected
- Kind is **not** part of the type system (no subtyping in function signatures)
- Kind checking is done at call sites via effect validation

### Operation Restrictions

| Kind | Can Measure? | Can Alloc? | Can Use Phase/Projections? |
|------|-------------|-----------|---------------------------|
| `pure fn` | ❌ No | ❌ No | ❌ No (classical only) |
| `unitary fn` | ❌ No | ❌ No | ✅ Yes |
| `mixed fn` | ✅ Yes | ✅ Yes | ✅ Yes |

**Note**: All three kinds can return any type or be void (`()`). Restrictions are on **operations allowed in the body**, not on return types.

### IR Representation

Each kind maps to a distinct operation in the `proj` dialect:

```mlir
proj.pure @classical_fn(...) attributes { ... }
proj.unitary @bell_pair(...) attributes { ... }
proj.mixed @teleport(...) attributes { ... }
```

**Benefits of separate operations**:
- IR-level verification (e.g., reject `proj.measure` in `proj.unitary`)
- Explicit semantics in operation name
- Enables kind-specific optimizations
- Clear intent when reading/generated IR



## Syntax Summary

| Concept | Syntax | Example |
|---------|--------|---------|
| Qubit type | `qubit` or `qubit<B>` | `q: qubit<Z>` |
| Projection type | `proj` | `p: proj` |
| Boolean type | `bool` | `b: bool` |
| Angle type | `angle` | `theta: angle` |
| Projection | `q == \|bool>` | `q == \|0>` or `q == \|0⟩` |
| Conjunction | `p1 && p2` | `p1 && p2` |
| Disjunction | `p1 \|\| p2` | `p1 \|\| p2` |
| XOR | `p1 ^ p2` | `p1 ^ p2` |
| Negation | `!p` | `!p` |
| Conditional | `if x { ... }` | `if p { phase(PI) }` or `if b { phase(PI) }` |
| Measurement | `measure(p)` | `let b: bool = measure(p)` |
| Allocation | `alloc \|bool>` | `let q = alloc \|0>` |
| Phase gate | `phase(theta)` | `phase(PI)` |
| Angle addition | `a1 + a2` | `PI + PI/2` |
| Angle subtraction | `a1 - a2` | `PI - PI/4` |
| Scalar mult | `c * a` | `2.0 * PI` |
| Scalar div | `a / c` | `PI / 3.0` |
| Angle constants | `PI`, `π`, `0` | `phase(PI)` |
| Pure function | `pure fn name(params) -> ret { ... }` | `pure fn f(b: bool) -> bool { ... }` |
| Unitary function | `unitary fn name(params) -> ret { ... }` | `unitary fn u(q: qubit) -> qubit { ... }` |
| Mixed function | `mixed fn name(params) -> ret { ... }` | `mixed fn m(q: qubit) -> bool { ... }` |

**Note**: State notation accepts both ASCII (`|0>`) and Unicode (`|0⟩`) syntax. Angle constant `PI` also accepts Unicode `π`.

**Subtyping**: `bool <: proj` - booleans are a subtype of projections. This means:
- Booleans can be used in `if` statements
- Boolean connectives (`&&`, `||`, `^`, `!`) work on both `bool` and `proj`
- Measurement results (`bool`) can be used directly in quantum conditionals

**Function Kinds**: `pure ⊆ unitary ⊆ mixed` - function kinds form a hierarchy. This means:
- `pure fn` can be called where `unitary fn` or `mixed fn` is expected
- `unitary fn` can be called where `mixed fn` is expected
- Kind is checked at call sites, not part of the type system
- IR uses separate operations: `proj.pure`, `proj.unitary`, `proj.mixed`

## References

- Quantum logic and projection lattices
- Rust borrow checker and lifetime elision
- MLIR dialect design patterns
- Linear and affine type systems
