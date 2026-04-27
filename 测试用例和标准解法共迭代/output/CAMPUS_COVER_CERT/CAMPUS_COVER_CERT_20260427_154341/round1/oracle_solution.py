import sys
sys.setrecursionlimit(3000)

def solve(input_str: str) -> str:
    data = input_str.split()
    if not data:
        return ""
    it = iter(data)
    x = int(next(it))
    q = int(next(it))

    teams = []
    next_id = 1
    out = []

    for _ in range(q):
        op = int(next(it))
        if op == 1:
            a = int(next(it))
            teams.append((next_id, a))
            next_id += 1
        else:
            K = int(next(it))
            violation = None
            for L in range(K):
                for R in range(L, K):
                    cnt = 0
                    for _, a in teams:
                        covers = False
                        for s in range(L, R + 1):
                            if s % x == a % x or s % x == (a + 1) % x:
                                covers = True
                                break
                        if covers:
                            cnt += 1
                    if cnt < R - L + 1:
                        violation = (L, R)
                        break
                if violation:
                    break

            if violation:
                out.append("NO")
                out.append(f"{violation[0]} {violation[1]}")
            else:
                match = {}
                used = set()
                slot_valid = []
                for s in range(K):
                    valid = []
                    for tid, a in teams:
                        if s % x == a % x or s % x == (a + 1) % x:
                            valid.append(tid)
                    slot_valid.append(valid)

                def dfs(slot):
                    if slot == K:
                        return True
                    for tid in slot_valid[slot]:
                        if tid not in used:
                            used.add(tid)
                            match[slot] = tid
                            if dfs(slot + 1):
                                return True
                            used.remove(tid)
                    return False

                if dfs(0):
                    out.append("YES")
                    for s in range(K):
                        out.append(f"{match[s]} {s}")
                else:
                    out.append("NO")
                    out.append("0 0")

    return "\n".join(out)