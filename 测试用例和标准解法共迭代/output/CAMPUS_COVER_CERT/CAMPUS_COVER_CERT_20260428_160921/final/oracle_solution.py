import sys


def solve(input_str: str) -> str:
    data = input_str.strip().split()
    if not data:
        return ''
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    teams = []
    out = []
    for _ in range(q):
        typ = int(next(it))
        if typ == 1:
            a = int(next(it))
            teams.append(a)
        else:
            K = int(next(it))
            n = len(teams)
            # Build bipartite graph: slots (0..K-1) -> team ids
            adj = [[] for _ in range(K)]
            for s in range(K):
                rem = s % x
                for tid, a in enumerate(teams, start=1):
                    r1 = a % x
                    r2 = (a + 1) % x
                    if rem == r1 or rem == r2:
                        adj[s].append(tid)
            # Hopcroft-Karp-like Hungarian algorithm for maximum matching
            match_r = [-1] * (n + 1)  # team id -> slot
            match_slot = [-1] * K

            def dfs(u, visited):
                for v in adj[u]:
                    if not visited[v]:
                        visited[v] = True
                        if match_r[v] == -1 or dfs(match_r[v], visited):
                            match_r[v] = u
                            match_slot[u] = v
                            return True
                return False

            max_match = 0
            for s in range(K):
                visited = [False] * (n + 1)
                if dfs(s, visited):
                    max_match += 1

            if max_match == K:
                out.append('YES')
                for s in range(K):
                    out.append(f'{match_slot[s]} {s}')
            else:
                out.append('NO')
                # Find lexicographically smallest violating interval [L,R]
                found = False
                for L in range(K):
                    for R in range(L, K):
                        covered = set()
                        for s in range(L, R + 1):
                            rem = s % x
                            for tid, a in enumerate(teams, start=1):
                                r1 = a % x
                                r2 = (a + 1) % x
                                if rem == r1 or rem == r2:
                                    covered.add(tid)
                        if len(covered) < R - L + 1:
                            out.append(f'{L} {R}')
                            found = True
                            break
                    if found:
                        break
                if not found:
                    # Fallback: if total teams < K, whole interval is violating
                    if n < K:
                        out.append(f'0 {K - 1}')
                    else:
                        # should not happen for a correct algorithm, but provide something valid
                        out.append('0 0')
    return '\n'.join(out)