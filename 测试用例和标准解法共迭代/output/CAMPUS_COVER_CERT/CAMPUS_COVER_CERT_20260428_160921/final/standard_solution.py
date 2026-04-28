import sys

class BIT:
    def __init__(self, n):
        self.n = n
        self.t = [0] * (n + 5)

    def add(self, i, delta):
        i += 1
        while i <= self.n:
            self.t[i] += delta
            i += i & -i

    def sum(self, i):
        i += 1
        res = 0
        while i > 0:
            res += self.t[i]
            i -= i & -i
        return res

    def range_sum(self, l, r):
        if l > r:
            return 0
        res = self.sum(r)
        if l > 0:
            res -= self.sum(l - 1)
        return res


def coverage(L, R, x, bit, total_teams):
    length = R - L + 1
    if length >= x:
        return total_teams
    s = (L - 1) % x
    t = R % x
    if s <= t:
        return bit.range_sum(s, t)
    else:
        return bit.range_sum(s, x - 1) + bit.range_sum(0, t)


def find_violation(K, x, bit, total_teams):
    best_L = None
    best_R = None
    max_L = min(x, K) - 1
    for L in range(max_L + 1):
        if coverage(L, L, x, bit, total_teams) < 1:
            if best_L is None or L < best_L:
                best_L = L
                best_R = L
            continue
        lo = L
        hi = K - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if coverage(L, mid, x, bit, total_teams) >= mid - L + 1:
                lo = mid + 1
            else:
                hi = mid
        if coverage(L, lo, x, bit, total_teams) < lo - L + 1:
            if best_L is None or L < best_L or (L == best_L and lo < best_R):
                best_L = L
                best_R = lo
    return best_L, best_R


def solve(input_str: str) -> str:
    data = list(map(int, input_str.split()))
    if not data:
        return ''
    it = iter(data)
    x = next(it)
    q = next(it)
    bit = BIT(x)

    team_by_rem = [[] for _ in range(x)]
    total_teams = 0
    id_counter = 0
    used_global = []
    last_used = []

    ptr = [0] * x
    out_lines = []
    query_id = 0

    for _ in range(q):
        typ = next(it)
        if typ == 1:
            a = next(it)
            r = a % x
            bit.add(r, 1)
            id_counter += 1
            team_by_rem[r].append(id_counter)
            total_teams += 1
            used_global.append(False)
            last_used.append(0)
        else:
            K = next(it)
            query_id += 1
            if total_teams < K:
                cnt_x1 = bit.range_sum(x - 1, x - 1)
                found = False
                for R in range(K):
                    if R >= x:
                        cov = total_teams
                    else:
                        cov = cnt_x1 + bit.range_sum(0, R)
                    if cov < R + 1:
                        out_lines.append(f'NO\n0 {R}')
                        found = True
                        break
                if not found:
                    out_lines.append(f'NO\n0 {K - 1}')
                continue

            # attempt construction
            cur_ptr = ptr[:]
            ans = []
            success = True
            for s in range(K):
                m = s % x
                tid = None
                # try list m
                while cur_ptr[m] < len(team_by_rem[m]):
                    cand = team_by_rem[m][cur_ptr[m]]
                    if used_global[cand - 1] or last_used[cand - 1] == query_id:
                        cur_ptr[m] += 1
                    else:
                        tid = cand
                        cur_ptr[m] += 1
                        break
                if tid is None:
                    prev = (m - 1) % x
                    while cur_ptr[prev] < len(team_by_rem[prev]):
                        cand = team_by_rem[prev][cur_ptr[prev]]
                        if used_global[cand - 1] or last_used[cand - 1] == query_id:
                            cur_ptr[prev] += 1
                        else:
                            tid = cand
                            cur_ptr[prev] += 1
                            break
                if tid is None:
                    success = False
                    break
                last_used[tid - 1] = query_id
                ans.append(f'{tid} {s}')

            if success:
                for line in ans:
                    tid_int = int(line.split()[0])
                    used_global[tid_int - 1] = True
                ptr = cur_ptr
                out_lines.append('YES')
                out_lines.extend(ans)
            else:
                L, R = find_violation(K, x, bit, total_teams)
                out_lines.append(f'NO\n{L} {R}')

    return '\n'.join(out_lines)


if __name__ == '__main__':
    input_data = sys.stdin.read()
    print(solve(input_data))