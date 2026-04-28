import sys

class SegmentTree:
    def __init__(self, n):
        self.n = n
        size = 1
        while size < n:
            size <<= 1
        self.size = size
        self.minv = [0] * (2 * size)
        self.pos = [0] * (2 * size)
        self.lazy = [0] * (2 * size)
        self._build(1, 0, size - 1)

    def _build(self, node, l, r):
        if l == r:
            if l < self.n:
                self.minv[node] = -l - 1
                self.pos[node] = l
            else:
                self.minv[node] = 10**18
                self.pos[node] = -1
            return
        mid = (l + r) // 2
        self._build(node * 2, l, mid)
        self._build(node * 2 + 1, mid + 1, r)
        self._pull(node)

    def _pull(self, node):
        left = node * 2
        right = node * 2 + 1
        if self.minv[left] <= self.minv[right]:
            self.minv[node] = self.minv[left]
            self.pos[node] = self.pos[left]
        else:
            self.minv[node] = self.minv[right]
            self.pos[node] = self.pos[right]

    def _apply(self, node, val):
        self.minv[node] += val
        self.lazy[node] += val

    def _push(self, node):
        if self.lazy[node] != 0:
            self._apply(node * 2, self.lazy[node])
            self._apply(node * 2 + 1, self.lazy[node])
            self.lazy[node] = 0

    def range_add(self, l, r, val):
        self._range_add(1, 0, self.size - 1, l, r, val)

    def _range_add(self, node, nl, nr, l, r, val):
        if r < nl or l > nr:
            return
        if l <= nl and nr <= r:
            self._apply(node, val)
            return
        self._push(node)
        mid = (nl + nr) // 2
        self._range_add(node * 2, nl, mid, l, r, val)
        self._range_add(node * 2 + 1, mid + 1, nr, l, r, val)
        self._pull(node)

    def query_min(self, l, r):
        if l > r:
            return (10**18, -1)
        return self._query_min(1, 0, self.size - 1, l, r)

    def _query_min(self, node, nl, nr, l, r):
        if r < nl or l > nr:
            return (10**18, -1)
        if l <= nl and nr <= r:
            return (self.minv[node], self.pos[node])
        self._push(node)
        mid = (nl + nr) // 2
        left_res = self._query_min(node * 2, nl, mid, l, r)
        right_res = self._query_min(node * 2 + 1, mid + 1, nr, l, r)
        if left_res[0] <= right_res[0]:
            return left_res
        return right_res

    def first_negative(self, l, r):
        if l > r:
            return -1
        return self._first_negative(1, 0, self.size - 1, l, r)

    def _first_negative(self, node, nl, nr, l, r):
        if r < nl or l > nr or self.minv[node] >= 0:
            return -1
        if nl == nr:
            return nl
        self._push(node)
        mid = (nl + nr) // 2
        left_res = self._first_negative(node * 2, nl, mid, l, r)
        if left_res != -1:
            return left_res
        return self._first_negative(node * 2 + 1, mid + 1, nr, l, r)


def solve(input_str: str) -> str:
    data = input_str.split()
    if not data:
        return ""
    it = iter(data)
    x = int(next(it))
    q = int(next(it))

    seg = SegmentTree(x)
    total_teams = 0
    team_mod = [[] for _ in range(x)]
    used = None
    id_counter = 0

    out_lines = []
    for _ in range(q):
        typ = int(next(it))
        if typ == 1:
            a = int(next(it))
            id_counter += 1
            r = a % x
            nxt = (r + 1) % x
            first = r if r < nxt else nxt
            seg.range_add(first, x - 1, 1)
            total_teams += 1
            team_mod[r].append(id_counter)
        else:
            K = int(next(it))
            if K == 0:
                out_lines.append("YES")
                continue
            found_neg = False
            conflict_R = -1
            query_r = min(K - 1, x - 1)
            min_val, min_pos = seg.query_min(0, query_r)
            if min_val < 0:
                conflict_R = seg.first_negative(0, query_r)
                found_neg = True
            else:
                if K > x and K > total_teams:
                    conflict_R = total_teams
                    found_neg = True
            if found_neg:
                out_lines.append(f"NO\n0 {conflict_R}")
            else:
                out_lines.append("YES")
                if used is None:
                    used = [False] * (id_counter + q + 5)
                ptrs = [0] * x
                for s in range(K):
                    m = s % x
                    tid = -1
                    lst_m = team_mod[m]
                    while ptrs[m] < len(lst_m) and used[lst_m[ptrs[m]]]:
                        ptrs[m] += 1
                    if ptrs[m] < len(lst_m):
                        tid = lst_m[ptrs[m]]
                        ptrs[m] += 1
                        used[tid] = True
                    else:
                        m2 = (m - 1) % x
                        lst_m2 = team_mod[m2]
                        while ptrs[m2] < len(lst_m2) and used[lst_m2[ptrs[m2]]]:
                            ptrs[m2] += 1
                        if ptrs[m2] < len(lst_m2):
                            tid = lst_m2[ptrs[m2]]
                            ptrs[m2] += 1
                            used[tid] = True
                    if tid == -1:
                        for cand in (m, (m - 1) % x):
                            for cid in team_mod[cand]:
                                if not used[cid]:
                                    tid = cid
                                    used[cid] = True
                                    break
                            if tid != -1:
                                break
                    out_lines.append(f"{tid} {s}")
    return "\n".join(out_lines)