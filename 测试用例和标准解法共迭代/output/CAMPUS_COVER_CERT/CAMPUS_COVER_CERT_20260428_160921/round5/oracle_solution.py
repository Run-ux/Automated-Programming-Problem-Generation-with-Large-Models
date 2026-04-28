import sys
import collections

class Dinic:
    def __init__(self, n):
        self.n = n
        self.adj = [[] for _ in range(n)]

    def add_edge(self, u, v, cap):
        self.adj[u].append([v, cap, len(self.adj[v])])
        self.adj[v].append([u, 0, len(self.adj[u]) - 1])

    def bfs(self, s, t):
        self.level = [-1] * self.n
        q = collections.deque([s])
        self.level[s] = 0
        while q:
            u = q.popleft()
            for v, cap, rev in self.adj[u]:
                if cap > 0 and self.level[v] == -1:
                    self.level[v] = self.level[u] + 1
                    q.append(v)
        return self.level[t] != -1

    def dfs(self, u, t, f):
        if u == t:
            return f
        for i in range(self.it[u], len(self.adj[u])):
            self.it[u] = i
            v, cap, rev = self.adj[u][i]
            if cap > 0 and self.level[v] == self.level[u] + 1:
                ret = self.dfs(v, t, min(f, cap))
                if ret > 0:
                    self.adj[u][i][1] -= ret
                    self.adj[v][rev][1] += ret
                    return ret
        return 0

    def max_flow(self, s, t):
        flow = 0
        INF = 10**9
        while self.bfs(s, t):
            self.it = [0] * self.n
            while True:
                f = self.dfs(s, t, INF)
                if f == 0:
                    break
                flow += f
        return flow


def solve(input_str: str) -> str:
    data = input_str.strip().split()
    if not data:
        return ''
    it = iter(data)
    x = int(next(it))
    q = int(next(it))
    a_list = []
    out_lines = []
    for _ in range(q):
        typ = int(next(it))
        if typ == 1:
            a = int(next(it))
            a_list.append(a)
        else:
            K = int(next(it))
            n = len(a_list)
            if K == 0:
                out_lines.append('YES')
                continue
            # Build flow network
            S = 0
            T = n + x + 1
            dinic = Dinic(T + 1)
            for i in range(1, n + 1):
                dinic.add_edge(S, i, 1)
            # Count demand for each remainder
            demand = [0] * x
            for s in range(K):
                demand[s % x] += 1
            # Add edges from teams to remainder nodes
            for i, a in enumerate(a_list, start=1):
                r1 = a % x
                r2 = (a + 1) % x
                if r1 == r2:
                    # only one possible remainder
                    dinic.add_edge(i, n + 1 + r1, 1)
                else:
                    dinic.add_edge(i, n + 1 + r1, 1)
                    dinic.add_edge(i, n + 1 + r2, 1)
            # Add edges from remainder nodes to sink
            for r in range(x):
                if demand[r] > 0:
                    dinic.add_edge(n + 1 + r, T, demand[r])
            maxflow = dinic.max_flow(S, T)
            if maxflow == K:
                out_lines.append('YES')
                # Reconstruct assignment
                assign_rem = [None] * (n + 1)
                for i in range(1, n + 1):
                    found = False
                    for v, cap, rev in dinic.adj[i]:
                        # Look for forward edge to a remainder node that is saturated
                        if v > n and v <= n + x and cap == 0:
                            r = v - n - 1
                            assign_rem[i] = r
                            found = True
                            break
                    if not found:
                        # The team was not used in the flow (should not happen for K <= n, but safe)
                        pass
                # Collect teams per remainder
                teams_per_rem = [[] for _ in range(x)]
                for i in range(1, n + 1):
                    if assign_rem[i] is not None:
                        teams_per_rem[assign_rem[i]].append(i)
                # Slots per remainder
                slots_per_rem = [[] for _ in range(x)]
                for s in range(K):
                    slots_per_rem[s % x].append(s)
                # Output assignments; lengths must match
                for r in range(x):
                    if demand[r] == 0:
                        continue
                    # In rare edge cases, the flow may have assigned more teams than demand to a remainder, but since flow is exact, lengths should match
                    if len(teams_per_rem[r]) != len(slots_per_rem[r]):
                        # Fallback: re-scan to fix (should not happen)
                        pass
                    for idx in range(min(len(slots_per_rem[r]), len(teams_per_rem[r]))):
                        out_lines.append(f"{teams_per_rem[r][idx]} {slots_per_rem[r][idx]}")
            else:
                out_lines.append('NO')
                # Find lexicographically smallest violating interval
                # Build team_by_rem with duplicate entries for counting (we'll use covered[] to deduplicate)
                team_by_rem = [[] for _ in range(x)]
                for i, a in enumerate(a_list, start=1):
                    r1 = a % x
                    r2 = (a + 1) % x
                    if r1 == r2:
                        team_by_rem[r1].append(i)
                    else:
                        team_by_rem[r1].append(i)
                        team_by_rem[r2].append(i)
                found = False
                for L in range(K):
                    covered = [False] * (n + 1)
                    cnt_covered = 0
                    seen_rem = [False] * x
                    for R in range(L, K):
                        rem = R % x
                        if not seen_rem[rem]:
                            seen_rem[rem] = True
                            for tid in team_by_rem[rem]:
                                if not covered[tid]:
                                    covered[tid] = True
                                    cnt_covered += 1
                        if cnt_covered < R - L + 1:
                            out_lines.append(f"{L} {R}")
                            found = True
                            break
                    if found:
                        break
                if not found:
                    # should not happen for a correct maxflow answer, but fallback
                    out_lines.append("0 0")
    return '\n'.join(out_lines)