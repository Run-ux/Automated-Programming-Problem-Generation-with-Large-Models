import sys
from collections import deque

def solve(input_str: str) -> str:
    data = list(map(int, input_str.split()))
    if not data:
        return ''
    it = iter(data)
    x = next(it)
    q = next(it)
    n = x

    cnt = [0] * n
    team_lists = [[] for _ in range(n)]
    team_a = [0]          # 1-indexed, team_a[tid] = a_i
    total_teams = 0
    id_counter = 0
    used = [0] * 100      # will extend dynamically
    out_lines = []
    qid = 0               # query id for timestamp

    pref_cnt = [0] * (n + 1)

    for _ in range(q):
        typ = next(it)
        if typ == 1:
            a_val = next(it)
            r = a_val % n
            cnt[r] += 1
            total_teams += 1
            id_counter += 1
            tid = id_counter
            team_a.append(a_val)
            team_lists[r].append(tid)
            team_lists[(r + 1) % n].append(tid)
        else:
            K = next(it)
            if K == 0:
                out_lines.append('YES')
                continue

            # ---------- trivial NO : total teams < K ----------
            if total_teams < K:
                # find smallest R such that coverage(0,R) < R+1
                # recompute prefix of cnt
                for i in range(n):
                    pref_cnt[i + 1] = pref_cnt[i] + cnt[i]
                best_R = -1
                # only need to check R up to total_teams, because after that
                # coverage cannot catch up
                max_R = min(K - 1, total_teams + n)
                for R in range(max_R + 1):
                    if R >= n:
                        cov = total_teams
                    else:
                        cov = pref_cnt[R + 1] - pref_cnt[0]
                        cov += cnt[n - 1]          # L=0  -> L-1 = n-1
                    if cov < R + 1:
                        best_R = R
                        break
                if best_R == -1:
                    best_R = K - 1
                out_lines.append(f'NO\n0 {best_R}')
                continue

            # ---------- total_teams >= K ----------
            # build demand array d
            full = K // n
            rem = K % n
            d = [full] * n
            for i in range(rem):
                d[i] += 1

            # net supply a[i] = cnt[i] - d[i]
            a = [cnt[i] - d[i] for i in range(n)]

            # prefix sums over 2n for sliding window
            pref = [0] * (2 * n + 1)
            for i in range(1, 2 * n + 1):
                pref[i] = pref[i - 1] + a[(i - 1) % n]

            # helper: O(1) coverage of interval [L,R] using current cnt
            def coverage(L, R):
                length = R - L + 1
                if length >= n:
                    return total_teams
                Lm = L % n
                Rm = R % n
                # sum cnt[L..R] (mod n)
                if Lm <= Rm:
                    cov = pref_cnt[Rm + 1] - pref_cnt[Lm]
                else:
                    cov = pref_cnt[n] - pref_cnt[Lm] + pref_cnt[Rm + 1]
                # add cnt[L-1]
                cov += cnt[(L - 1) % n]
                return cov

            # recompute prefix of cnt (used by coverage and by sliding window)
            for i in range(n):
                pref_cnt[i + 1] = pref_cnt[i] + cnt[i]

            # sliding window length = min(K, n)
            w = min(K, n)
            dq = deque()

            # check L = 0 first
            for idx in range(1, w + 1):
                while dq and pref[dq[-1]] >= pref[idx]:
                    dq.pop()
                dq.append(idx)
            target = pref[0] - cnt[n - 1]      # L=0  -> L-1 = n-1
            if pref[dq[0]] < target:
                # violation for L=0
                for R in range(0, min(K, n)):
                    if coverage(0, R) < R + 1:
                        out_lines.append(f'NO\n0 {R}')
                        break
                continue

            found_violation = False
            limit_L = min(n, K)
            for L in range(1, limit_L):
                target = pref[L] - cnt[(L - 1) % n]
                # remove indices < L+1
                while dq and dq[0] < L + 1:
                    dq.popleft()
                new_idx = L + w
                if new_idx <= 2 * n:
                    while dq and pref[dq[-1]] >= pref[new_idx]:
                        dq.pop()
                    dq.append(new_idx)
                if pref[dq[0]] < target:
                    # violation for this L
                    max_R = min(K - 1, L + n - 1)
                    for R in range(L, max_R + 1):
                        if coverage(L, R) < R - L + 1:
                            out_lines.append(f'NO\n{L} {R}')
                            found_violation = True
                            break
                    if found_violation:
                        break
            if found_violation:
                continue

            # ---------- feasible (YES) ----------
            qid += 1
            if len(used) <= id_counter:
                used.extend([0] * (id_counter + 10 - len(used)))
            ans = ['YES']
            ptrs = [0] * n   # reset pointers for this query
            for s in range(K):
                m = s % n
                tid = -1
                # try list of previous remainder (more constrained)
                prev = (m - 1) % n
                while ptrs[prev] < len(team_lists[prev]):
                    cand = team_lists[prev][ptrs[prev]]
                    ptrs[prev] += 1
                    if used[cand] != qid:
                        a_i = team_a[cand]
                        r1 = a_i % n
                        r2 = (a_i + 1) % n
                        if r1 == m or r2 == m:
                            tid = cand
                            used[tid] = qid
                            break
                if tid == -1:
                    while ptrs[m] < len(team_lists[m]):
                        cand = team_lists[m][ptrs[m]]
                        ptrs[m] += 1
                        if used[cand] != qid:
                            a_i = team_a[cand]
                            r1 = a_i % n
                            r2 = (a_i + 1) % n
                            if r1 == m or r2 == m:
                                tid = cand
                                used[tid] = qid
                                break
                if tid == -1:
                    # fallback: scan all remainder lists (rare)
                    for i in range(n):
                        while ptrs[i] < len(team_lists[i]):
                            cand = team_lists[i][ptrs[i]]
                            ptrs[i] += 1
                            if used[cand] != qid:
                                a_i = team_a[cand]
                                r1 = a_i % n
                                r2 = (a_i + 1) % n
                                if r1 == m or r2 == m:
                                    tid = cand
                                    used[tid] = qid
                                    break
                        if tid != -1:
                            break
                if tid != -1:
                    ans.append(f'{tid} {s}')
                else:
                    # should never happen because we already proved feasible
                    ans.append('-1 {s}')
            out_lines.append('\n'.join(ans))

    return '\n'.join(out_lines)


if __name__ == '__main__':
    input_data = sys.stdin.read()
    print(solve(input_data))