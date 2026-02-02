//! Benchmarks for Firefly Core Hamming operations.

use criterion::{black_box, criterion_group, criterion_main, Criterion, BenchmarkId};
use firefly_core::{HammingVector, bundle, resonate, fingerprint};

fn bench_from_seed(c: &mut Criterion) {
    c.bench_function("HammingVector::from_seed", |b| {
        b.iter(|| HammingVector::from_seed(black_box("test_seed_string")))
    });
}

fn bench_hamming_distance(c: &mut Criterion) {
    let v1 = HammingVector::from_seed("vector_a");
    let v2 = HammingVector::from_seed("vector_b");

    c.bench_function("hamming_distance", |b| {
        b.iter(|| black_box(&v1).hamming(black_box(&v2)))
    });
}

fn bench_xor(c: &mut Criterion) {
    let v1 = HammingVector::from_seed("vector_a");
    let v2 = HammingVector::from_seed("vector_b");

    c.bench_function("xor_binding", |b| {
        b.iter(|| black_box(&v1) ^ black_box(&v2))
    });
}

fn bench_similarity(c: &mut Criterion) {
    let v1 = HammingVector::from_seed("vector_a");
    let v2 = HammingVector::from_seed("vector_b");

    c.bench_function("similarity", |b| {
        b.iter(|| black_box(&v1).similarity(black_box(&v2)))
    });
}

fn bench_bundle(c: &mut Criterion) {
    let mut group = c.benchmark_group("bundle");

    for count in [3, 5, 10, 20].iter() {
        let vectors: Vec<HammingVector> = (0..*count)
            .map(|i| HammingVector::from_seed(&format!("vec_{}", i)))
            .collect();

        group.bench_with_input(BenchmarkId::from_parameter(count), &vectors, |b, vecs| {
            b.iter(|| bundle(black_box(vecs)))
        });
    }

    group.finish();
}

fn bench_resonate(c: &mut Criterion) {
    let mut group = c.benchmark_group("resonate");

    for corpus_size in [100, 1000, 10000].iter() {
        let query = HammingVector::from_seed("query");
        let corpus: Vec<HammingVector> = (0..*corpus_size)
            .map(|i| HammingVector::from_seed(&format!("item_{}", i)))
            .collect();

        group.bench_with_input(
            BenchmarkId::from_parameter(corpus_size),
            &(&query, &corpus),
            |b, (q, c)| {
                b.iter(|| resonate(black_box(*q), black_box(*c), 0.5))
            },
        );
    }

    group.finish();
}

fn bench_fingerprint(c: &mut Criterion) {
    c.bench_function("fingerprint", |b| {
        b.iter(|| {
            fingerprint(
                black_box("validate_email"),
                black_box("(str) -> bool"),
                black_box("check email format with regex"),
            )
        })
    });
}

fn bench_hex_roundtrip(c: &mut Criterion) {
    let v = HammingVector::from_seed("test");

    c.bench_function("to_hex", |b| {
        b.iter(|| black_box(&v).to_hex())
    });

    let hex = v.to_hex();
    c.bench_function("from_hex", |b| {
        b.iter(|| HammingVector::from_hex(black_box(&hex)))
    });
}

criterion_group!(
    benches,
    bench_from_seed,
    bench_hamming_distance,
    bench_xor,
    bench_similarity,
    bench_bundle,
    bench_resonate,
    bench_fingerprint,
    bench_hex_roundtrip,
);

criterion_main!(benches);
