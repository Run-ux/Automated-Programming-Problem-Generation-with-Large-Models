import sys

def solve(input_str: str) -> str:
    data = input_str.split()
    if not data:
        return ""
    it = iter(data)
    try:
        x = int(next(it))
        q = int(next(it))
    except StopIteration:
        return ""

    cnt = [0] * x
    teams = []  # (id, r)
    total_teams = 0
    out_lines = []

    for _ in range(q):
        try:
            typ = int(next(it))
            val = int(next(it))
        except StopIteration:
            break

        if typ == 1:
            r = val % x
            cnt[r] += 1
            total_teams += 1
            teams.append((total_teams, r))
        else:
            K = val
            if K > total_teams:
                out_lines.append("NO")
                out_lines.append(f"0 {total_teams}")
                continue

            # Greedy assignment for slots 0..K-1
            # queues[r] stores indices of teams with residue r
            queues = [[] for _ in range(x)]
            for idx, (_, r) in enumerate(teams):
                queues[r].append(idx)

            assigned = []
            used = [False] * (total_teams + 1)
            possible = True
            fail_s = K

            for s in range(K):
                r = s % x
                prev_r = (r - 1) % x
                found = False
                # Prefer prev_r (covers s but not s+1) to save r for future
                for qr in (prev_r, r):
                    while queues[qr] and used[teams[queues[qr][0]][0]]:
                        queues[qr].pop(0)
                    if queues[qr]:
                        idx = queues[qr].pop(0)
                        tid = teams[idx][0]
                        used[tid] = True
                        assigned.append((tid, s))
                        found = True
                        break
                if not found:
                    possible = False
                    fail_s = s
                    break

            if possible:
                out_lines.append("YES")
                for tid, s in assigned:
                    out_lines.append(f"{tid} {s}")
            else:
                # Find lexicographically smallest [L, R] violating Hall's condition
                limit = min(fail_s + 1, 2000)
                best_L, best_R = 0, fail_s
                found_violation = False

                # Precompute residues with teams for faster counting
                present_rs = [r for r in range(x) if cnt[r] > 0]

                for L in range(limit):
                    cur_count = 0
                    # Track covered residues in current [L, R]
                    covered = set()
                    for R in range(L, limit):
                        r1 = R % x
                        r2 = (R - 1) % x
                        # Add newly covered residues
                        if r1 not in covered:
                            covered.add(r1)
                            cur_count += cnt[r1]
                        if r2 not in covered:
                            covered.add(r2)
                            cur_count += cnt[r2]

                        if cur_count < R - L + 1:
                            best_L, best_R = L, R
                            found_violation = True
                            break
                    if found_violation:
                        break

                out_lines.append("NO")
                out_lines.append(f"{best_L} {best_R}")

    return "\n".join(out_lines)