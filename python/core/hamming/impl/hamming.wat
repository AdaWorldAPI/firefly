;; 10K Hamming Operations - WebAssembly
(module
  ;; Constants
  (global $DIM i32 (i32.const 10000))
  (global $DIM_U64 i32 (i32.const 157))
  (global $LAST_MASK i64 (i64.const 65535))
  
  ;; Memory: 2 vectors (157 * 8 * 2 = 2512 bytes min)
  (memory (export "memory") 1)
  
  ;; popcount64 - count set bits
  (func $popcount64 (param $x i64) (result i32)
    (local $count i32)
    (local.set $count (i32.const 0))
    (block $done
      (loop $loop
        (br_if $done (i64.eqz (local.get $x)))
        (local.set $count 
          (i32.add (local.get $count)
            (i32.wrap_i64 (i64.and (local.get $x) (i64.const 1)))))
        (local.set $x (i64.shr_u (local.get $x) (i64.const 1)))
        (br $loop)
      )
    )
    (local.get $count)
  )
  
  ;; hamming distance between vectors at offsets a and b
  (func $hamming (export "hamming") (param $a i32) (param $b i32) (result i32)
    (local $total i32)
    (local $i i32)
    (local $xa i64)
    (local $xb i64)
    
    (local.set $total (i32.const 0))
    (local.set $i (i32.const 0))
    
    (block $done
      (loop $loop
        (br_if $done (i32.ge_u (local.get $i) (global.get $DIM_U64)))
        
        ;; Load 64-bit values
        (local.set $xa (i64.load (i32.add (local.get $a) (i32.mul (local.get $i) (i32.const 8)))))
        (local.set $xb (i64.load (i32.add (local.get $b) (i32.mul (local.get $i) (i32.const 8)))))
        
        ;; XOR and popcount
        (local.set $total 
          (i32.add (local.get $total)
            (call $popcount64 (i64.xor (local.get $xa) (local.get $xb)))))
        
        (local.set $i (i32.add (local.get $i) (i32.const 1)))
        (br $loop)
      )
    )
    
    (local.get $total)
  )
  
  ;; similarity as fixed-point (multiply by 10000 for precision)
  (func $similarity_fp (export "similarity_fp") (param $a i32) (param $b i32) (result i32)
    (i32.sub 
      (global.get $DIM)
      (call $hamming (local.get $a) (local.get $b)))
  )
)