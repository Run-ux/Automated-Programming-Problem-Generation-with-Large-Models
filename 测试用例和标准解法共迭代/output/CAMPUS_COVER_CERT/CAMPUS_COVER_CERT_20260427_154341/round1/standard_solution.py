import sys

sys.setrecursionlimit(300000)

def solve(input_str: str) -> str:
    data = input_str.split()
    it = iter(data)
    try:
        x = int(next(it))
        q = int(next(it))
    except StopIteration:
        return ""

    n = x
    size = 4 * n
    tree = [0] * size
    lazy = [0] * size

    def build(node, l, r):
        if l == r:
            tree[node] = -(l + 1)
            return
        mid = (l + r) // 2
        build(2 * node, l, mid)
        build(2 * node + 1, mid + 1, r)
        tree[node] = min(tree[2 * node], tree[2 * node + 1])

    def push(node):
        if lazy[node] != 0:
            lz = lazy[node]
            tree[2 * node] += lz
            lazy[2 * node] += lz
            tree[2 * node + 1] += lz
            lazy[2 * node + 1] += lz
            lazy[node] = 0

    def update(node, l, r, ql, qr, val):
        if ql <= l and r <= qr:
            tree[node] += val
            lazy[node] += val
            return
        push(node)
        mid = (l + r) // 2
        if ql <= mid:
            update(2 * node, l, mid, ql, qr, val)
        if qr > mid:
            update(2 * node + 1, mid + 1, r, ql, qr, val)
        tree[node] = min(tree[2 * node], tree[2 * node + 1])

    def find_first_neg(node, l, r, limit):
        if tree[node] >= 0 or l > limit:
            return -1
        if l == r:
            return l
        push(node)
        mid = (l + r) // 2
        res = find_first_neg(2 * node, l, mid, limit)
        if res != -1:
            return res
        return find_first_neg(2 * node + 1, mid + 1, r, limit)

    build(1, 0, n - 1)

    teams = [[] for _ in range(x)]
    total_teams = 0
    out = []

    for _ in range(q):
        typ = int(next(it))
        if typ == 1:
            a = int(next(it))
            r = a % x
            teams[r].append(total_teams + 1)
            total_teams += 1
            if r < n:
                update(1, 0, n - 1, r, n - 1, 1)
        else:
            K = int(next(it))
            limit = min(K - 1, n - 1)
            idx = find_first_neg(1, 0, n - 1, limit)
            if idx != -1:
                out.append("NO")
                out.append(f"0 {idx}")
            elif total_teams < K:
                out.append("NO")
                out.append(f"0 {total_teams}")
            else:
                out.append("YES")
                for s in range(K):
                    r = s % x
                    prev_r = (r - 1) % x
                    tid = -1
                    if prev_r != r and teams[prev_r]:
                        tid = teams[prev_r].pop()
                    elif teams[r]:
                        tid = teams[r].pop()
                    out.append(f"{tid} {s}")

    return "\n".join(out) + "\n"