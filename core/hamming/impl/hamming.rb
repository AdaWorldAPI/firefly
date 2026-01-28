# 10K Hamming Operations - Ruby
module Hamming
  DIM = 10_000
  DIM_U64 = 157
  LAST_MASK = (1 << 16) - 1

  def self.popcount64(x)
    x.to_s(2).count('1')
  end

  def self.distance(a, b)
    total = 0
    DIM_U64.times do |i|
      total += popcount64(a[i] ^ b[i])
    end
    total
  end

  def self.similarity(a, b)
    1.0 - distance(a, b).to_f / DIM
  end

  def self.xor_bind(a, b)
    result = DIM_U64.times.map { |i| a[i] ^ b[i] }
    result[-1] &= LAST_MASK
    result
  end

  def self.batch_distance(query, corpus)
    corpus.map { |vec| distance(query, vec) }
  end

  Match = Struct.new(:index, :similarity)

  def self.resonate(query, corpus, threshold = 0.5)
    results = []
    corpus.each_with_index do |vec, i|
      sim = similarity(query, vec)
      results << Match.new(i, sim) if sim >= threshold
    end
    results.sort_by { |m| -m.similarity }
  end
end