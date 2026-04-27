def generate_tests() -> list[dict]:
    import random
    random.seed(42)
    tests = []
    
    def make_test(inp, src, purpose, expect_oracle, is_sample, is_large, meta):
        tests.append({
            'input': inp,
            'source': src,
            'purpose': purpose,
            'expect_oracle': expect_oracle,
            'is_sample': is_sample,
            'is_large': is_large,
            'metadata': meta
        })
    
    # 1. basic_small
    make_test('3 4\n1 0\n1 1\n2 2\n2 3', 'problem_statement', 'Basic YES/NO branching and formatting', True, True, False, {'bucket': 'basic_small'})
    make_test('5 4\n1 0\n1 3\n1 3\n2 4', 'problem_statement', 'NO case with non-trivial minimal interval', True, True, False, {'bucket': 'basic_small'})
    make_test('2 3\n1 0\n2 1\n2 2', 'generated', 'Minimal x=2, single team coverage', True, False, False, {'bucket': 'basic_small'})
    
    # 2. boundary_values
    make_test('1 2\n1 0\n2 1', 'generated', 'x=1 boundary, all slots equivalent', True, False, False, {'bucket': 'boundary_values'})
    make_test('400000 1\n2 1', 'generated', 'Max x, immediate query with no teams', True, False, False, {'bucket': 'boundary_values'})
    make_test('10 3\n1 1000000000\n1 0\n2 1', 'generated', 'Max a_i boundary, modulo wrap', True, False, False, {'bucket': 'boundary_values'})
    
    # 3. random_mixed
    for i in range(3):
        x = random.randint(2, 100)
        q = random.randint(5, 20)
        lines = [f'{x} {q}']
        teams = []
        for _ in range(q):
            if random.random() < 0.6 or not teams:
                a = random.randint(0, 1000)
                teams.append(a)
                lines.append(f'1 {a}')
            else:
                K = random.randint(1, min(50, len(teams) + 2))
                lines.append(f'2 {K}')
        make_test('\n'.join(lines), 'random_mixed', f'Random mixed ops (seed {i})', True, False, False, {'bucket': 'random_mixed', 'seed': i})
    
    # 4. adversarial_hall
    make_test('4 3\n1 0\n1 2\n2 4', 'generated', 'Forces NO with gap at residue 1,3', True, False, False, {'bucket': 'adversarial_hall'})
    make_test('6 4\n1 0\n1 1\n1 4\n2 5', 'generated', 'Sparse coverage forcing minimal violation at [2,3]', True, False, False, {'bucket': 'adversarial_hall'})
    
    # 5. performance_large
    x = 400000
    q = 400000
    lines = [f'{x} {q}']
    for i in range(1, q):
        lines.append(f'1 {i % x}')
    lines.append(f'2 {1000000000}')
    make_test('\n'.join(lines), 'performance_large', 'Max q, large K NO query', False, False, True, {'bucket': 'performance_large', 'sum_K_yes': 0})
    
    # YES performance test (sum K <= 4e5)
    x = 1000
    q = 2000
    lines = [f'{x} {q}']
    for i in range(1, 1001):
        lines.append(f'1 {i}')
    for _ in range(1000):
        lines.append(f'2 {400}')
    make_test('\n'.join(lines), 'performance_large', 'Max sum K YES queries', False, False, True, {'bucket': 'performance_large', 'sum_K_yes': 400000})
    
    return tests