#pragma once
#include <algorithm>
#include <thread>
#include <vector>

namespace ag {

// Run f(rowBegin, rowEnd) over [y0, y1) split into bands across hardware threads.
template <class F>
void parallelRows(int y0, int y1, F&& f) {
    int rows = y1 - y0;
    unsigned hw = std::max(1u, std::thread::hardware_concurrency());
    int bands = int(std::min<unsigned>(hw, unsigned(std::max(1, rows / 32))));
    if (bands <= 1) {
        f(y0, y1);
        return;
    }
    std::vector<std::thread> pool;
    pool.reserve(size_t(bands) - 1);
    int step = (rows + bands - 1) / bands;
    for (int b = 1; b < bands; b++) {
        int a = y0 + b * step, e = std::min(y1, a + step);
        if (a < e) pool.emplace_back([&f, a, e] { f(a, e); });
    }
    f(y0, std::min(y1, y0 + step));
    for (auto& t : pool) t.join();
}

}  // namespace ag
