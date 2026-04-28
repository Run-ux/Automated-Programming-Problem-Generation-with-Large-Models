import sys
from collections import deque

class Solver:
    def __init__(self):
        pass

    def solve(self, input_str: str) -> str:
        data = list(map(int, input_str.split()))
        if not data:
            return ''
        it = iter(data)
        x = next(it)
        q = next(it)

        cnt = [0] * x                     # cnt[r] = number of teams with a % x == r
        team_lists = [[] for _ in range(x)]
        # each team id will be appended to team_lists[r] and team_lists[(r+1)%x]

        total_teams = 0
        id_counter = 0
        used = []
        query_id = 0

        out_lines = []

        for _ in range(q):
            typ = next(it)
            if typ == 1:
                a = next(it)
                r = a % x
                cnt[r] += 1
                total_teams += 1
                id_counter += 1
                tid = id_counter
                team_lists[r].append(tid)
                team_lists[(r + 1) % x].append(tid)
            else:
                K = next(it)
                if K == 0:
                    out_lines.append('YES')
                    continue
                if K > total_teams:
                    # total teams insufficient: answer is NO, find smallest R with [0,R] violated
                    # R will be <= total_teams because at R=total_teams the demand > total_teams
                    # compute coverage of [0,R] quickly
                    pref = [0] * x
                    pref[0] = cnt[0]
                    for i in range(1, x):
                        pref[i] = pref[i-1] + cnt[i]
                    best_R = -1
                    for R in range(min(K-1, total_teams + 1)):  # R up to total_teams surely enough
                        if R < x:
                            cov = pref[R]
                            if R < x - 1:
                                cov += cnt[x-1]   # team with r=x-1 covers slot 0
                            else:
                                pass  # already includes cnt[x-1]
                        else:
                            cov = total_teams
                        if cov < R + 1:
                            best_R = R
                            break
                    if best_R == -1:
                        best_R = K - 1  # fallback
                    out_lines.append(f'NO\n0 {best_R}')
                    continue

                # total_teams >= K
                # Determine if it is possible (YES) or not, and if NO, find lexicographically smallest conflict interval.
                # We will use the dual of Hall's condition: a greedy scan over the cycle works.
                query_id += 1
                if len(used) <= id_counter:
                    used.extend([0] * (id_counter + 5 - len(used)))

                # Build demand array d for one period
                full = K // x
                rem = K % x
                d = [full] * x
                for i in range(rem):
                    d[i] += 1

                # Check feasibility and find violation interval
                # We do a greedy scan on double length array to cover all possibilities
                n = x
                a = [cnt[i] - d[i] for i in range(n)]  # net supply per residue
                # Double it
                a2 = a + a
                # prefix sums
                P = [0] * (2 * n)
                P[0] = a2[0]
                for i in range(1, 2 * n):
                    P[i] = P[i-1] + a2[i]

                # For each possible start L (0 <= L < n) we check if there exists R in [L, L+n-1] such that 
                # cnt[L-1] + sum_{i=L}^{R} a[i] < 0  (mod n)
                # using sliding window minimum
                # We need to compute best violation interval (L,R) with smallest L, then smallest R.
                INF = 10**18
                best_L = K
                best_R = K

                # We use a deque of indices
                dq = deque()
                # We will move L from 0 to n-1 and maintain window of length n
                # but condition involves cnt[L-1] as initial pool.
                # Let's transform: define B[i] = P[i] + cnt[(i+1)%n]? Not straightforward.
                # Instead we can enumerate all possible L from 0 to min(K-1, n-1) and try to find the smallest R in [L, L+?]
                # Because K may be > n, but the first violation will appear within the first period for L?
                # Actually a violation may appear in later periods. The dictionary order of intervals (L,R) requires L minimal,
                # then R minimal. Since the problem is periodic with period x, the minimal L will be < x if K >= x?
                # Not always, but we can limit L to 0..min(K-1, n-1) because if L >= n, then interval [L,R] has an equivalent interval 
                # [L-n, R-n] with smaller L, so dictionary order ensures we only need to consider L < x (and L < K).
                # So we enumerate L from 0 to min(K-1, x-1).
                max_L = min(K-1, x-1)

                # Precompute prefix sum of cnt
                pref_cnt = [0] * (n + 1)
                for i in range(n):
                    pref_cnt[i+1] = pref_cnt[i] + cnt[i]

                def coverage(L, R):
                    # L,R are residues, compute how many teams can cover this residue interval
                    # R may be >= n, but for residue we take mod.
                    length = R - L + 1
                    # compute how many teams have at least one residue in [L, R]
                    # teams with a%x == i are counted if i in [L,R] or i+1 in [L,R]
                    # It's easier: sum cnt[i] for i in [L,R] plus cnt[L-1] (if L>0 else cnt[n-1]) plus cnt[R+1] if R< n-1 etc.
                    # But here L,R are residues, we assume R < x (we can restrict search to R < x for first violation? 
                    # Actually we can find a violation within one period length, so R-L+1 <= x.
                    # So we can just compute the exact coverage for residues only.
                    if R >= n:
                        return -1  # not needed
                    cov = pref_cnt[R+1] - pref_cnt[L]
                    if L == 0:
                        cov += cnt[n-1]
                    else:
                        cov += cnt[L-1]
                    if R < n - 1:
                        cov += cnt[R+1]
                    return cov

                found = False
                for L in range(max_L + 1):
                    # Find smallest R >= L such that coverage(L,R) < R-L+1 and R < K
                    # We can try R from L up to min(K-1, L + x - 1) (since interval length > x would be redundant)
                    # and if not found, maybe larger R? but then periodicity would give equivalent violation with smaller L.
                    # So we only need to check R up to L + x - 1.
                    max_R = min(K-1, L + x - 1)
                    for R in range(L, max_R + 1):
                        if coverage(L, R % x) < (R - L + 1):
                            if L < best_L or (L == best_L and R < best_R):
                                best_L, best_R = L, R
                            break  # first R for this L, move to next L
                    if best_L == 0:
                        # if we already found L=0, that is the smallest possible L, we can stop
                        found = True
                        break
                if best_L < K:
                    found = True

                if found:
                    out_lines.append(f'NO\n{best_L} {best_R}')
                else:
                    # YES: construct a valid assignment
                    # Use greedy with persistent pointers and time-stamp used
                    # We need to know the starting L for allocation (which we can determine from feasibility)
                    # But since we didn't track a valid L during feasibility, we can compute one using the same greedy scan on the cycle.
                    # Alternatively, we can just use the allocation algorithm described below without needing a specific L.
                    # The construction algorithm handles any L by just mapping slot numbers.
                    
                    # Build the answer
                    ans_lines = ['YES']
                    # temporary arrays for allocation
                    if not hasattr(self, 'ptrs'):
                        self.ptrs = [0] * n
                    ptrs = self.ptrs   # persistent pointers for team_lists
                    # We will process slots from 0 to K-1
                    # For each slot s, its residue is m = s % x
                    for s in range(K):
                        m = s % x
                        tid = -1
                        # first try list from previous residue (m-1) because those teams are more constrained
                        prev = (m - 1) % n
                        while ptrs[prev] < len(team_lists[prev]):
                            cand = team_lists[prev][ptrs[prev]]
                            ptrs[prev] += 1
                            if used[cand] != query_id:
                                tid = cand
                                used[tid] = query_id
                                break
                        if tid == -1:
                            # try current residue list
                            while ptrs[m] < len(team_lists[m]):
                                cand = team_lists[m][ptrs[m]]
                                ptrs[m] += 1
                                if used[cand] != query_id:
                                    tid = cand
                                    used[tid] = query_id
                                    break
                        if tid == -1:
                            # should not happen because we verified feasibility
                            # fallback: linear scan all teams (should not be needed)
                            for i in range(n):
                                while ptrs[i] < len(team_lists[i]):
                                    cand = team_lists[i][ptrs[i]]
                                    ptrs[i] += 1
                                    if used[cand] != query_id:
                                        tid = cand
                                        used[tid] = query_id
                                        break
                                if tid != -1:
                                    break
                        if tid == -1:
                            # if still not found, something went wrong, output dummy to avoid crash
                            ans_lines.append(f'-1 {s}')
                        else:
                            ans_lines.append(f'{tid} {s}')
                    out_lines.append('\n'.join(ans_lines))

        return '\n'.join(out_lines)


def solve(input_str: str) -> str:
    solver = Solver()
    return solver.solve(input_str)