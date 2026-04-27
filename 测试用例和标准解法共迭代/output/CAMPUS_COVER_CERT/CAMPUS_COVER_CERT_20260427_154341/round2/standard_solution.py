import sys
sys.setrecursionlimit(1000000)

def solve(input_str: str) -> str:
    data = input_str.split()
    it = iter(data)
    try:
        x = int(next(it))
        q = int(next(it))
    except StopIteration:
        return ""

    size = 1
    while size < x:
        size *= 2

    tree = [0] * (2 * size)
    lazy = [0] * (2 * size)

    for i in range(size):
        if i < x:
            tree[size + i] = -(i + 1)
        else:
            tree[size + i] = float('inf')

    for i in range(size - 1, 0, -1):
        tree[i] = min(tree[2*i], tree[2*i+1])

    def push(node):
        lz = lazy[node]
        if lz != 0:
            lazy[2*node] += lz
            tree[2*node] += lz
            lazy[2*node+1] += lz
            tree[2*node+1] += lz
            lazy[node] = 0

    def update(node, l, r, ql, qr, val):
        if ql > r or qr < l:
            return
        if ql <= l and r <= qr:
            tree[node] += val
            lazy[node] += val
            return
        push(node)
        mid = (l + r) // 2
        update(2*node, l, mid, ql, qr, val)
        update(2*node+1, mid+1, r, ql, qr, val)
        tree[node] = min(tree[2*node], tree[2*node+1])

    def query_min(node, l, r, ql, qr):
        if ql > r or qr < l:
            return float('inf')
        if ql <= l and r <= qr:
            return tree[node]
        push(node)
        mid = (l + r) // 2
        return min(query_min(2*node, l, mid, ql, qr),
                   query_min(2*node+1, mid+1, r, ql, qr))

    def find_first_neg(node, l, r, limit):
        if l > limit or tree[node] >= 0:
            return -1
        if l == r:
            return l
        push(node)
        mid = (l + r) // 2
        res = find_first_neg(2*node, l, mid, limit)
        if res != -1:
            return res
        return find_first_neg(2*node+1, mid+1, r, limit)

    teams = [[] for _ in range(x)]
    ptr = [0] * x
    team_id = 0
    total_teams = 0
    out = []

    for _ in range(q):
        typ = int(next(it))
        val = int(next(it))
        if typ == 1:
            team_id += 1
            total_teams += 1
            r = val % x
            teams[r].append(team_id)
            update(1, 0, size-1, r, size-1, 1)
        else:
            K = val
            limit = min(K - 1, x - 1)
            if limit < 0:
                out.append("YES")
                continue

            mn = query_min(1, 0, size-1, 0, limit)
            if mn < 0:
                R = find_first_neg(1, 0, size-1, limit)
                out.append("NO")
                out.append(f"0 {R}")
            else:
                if total_teams < K:
                    out.append("NO")
                    out.append(f"0 {total_teams}")
                else:
                    out.append("YES")
                    assigned = []
                    for s in range(K):
                        r1 = s % x
                        r2 = (s - 1) % x
                        if ptr[r1] < len(teams[r1]):
                            tid = teams[r1][ptr[r1]]
                            ptr[r1] += 1
                        else:
                            tid = teams[r2][ptr[r2]]
                            ptr[r2] += 1
                        assigned.append(f"{tid} {s}")
                    out.append("\n".join(assigned))

    return "\n".join(out)