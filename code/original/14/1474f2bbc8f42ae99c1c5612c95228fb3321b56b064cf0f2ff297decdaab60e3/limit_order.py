"""Own limit-order repair. No process creation, imports of solver code or arithmetic."""
import resource

class LimitOrderError(RuntimeError):
    pass

def plan_limits(role_limits, inherited):
    if set(role_limits) != {'supervisor', 'broker', 'perl'}:
        raise LimitOrderError('STOP_ROLE_SET')
    names = tuple(role_limits['supervisor'])
    if any(set(role_limits[role]) != set(names) for role in role_limits):
        raise LimitOrderError('STOP_LIMIT_KEY_SET')
    for role, limits in role_limits.items():
        for name, pair in limits.items():
            if len(pair) != 2 or any(type(x) is not int or x < 0 for x in pair) or pair[0] > pair[1]:
                raise LimitOrderError('STOP_LIMIT_PAIR:' + role + ':' + name)
    staged = {}
    for name in names:
        hard = max(role_limits[role][name][1] for role in role_limits)
        current_hard = inherited[name][1]
        if current_hard != resource.RLIM_INFINITY and current_hard < hard:
            raise LimitOrderError('STOP_INHERITED_HARD:' + name)
        # Effective supervisor soft cap is never raised above the frozen value.
        staged[name] = [role_limits['supervisor'][name][0], hard]
    return staged

def prepare_supervisor_limits(role_limits):
    before = {name: list(resource.getrlimit(getattr(resource, name))) for name in role_limits['supervisor']}
    staged = plan_limits(role_limits, before)  # Validate every hard ceiling before any mutation.
    for name, pair in staged.items():
        resource.setrlimit(getattr(resource, name), tuple(pair))
    actual = {name: list(resource.getrlimit(getattr(resource, name))) for name in staged}
    if actual != staged:
        raise LimitOrderError('STOP_STAGED_EFFECTIVE_LIMITS')
    return {'inherited': before, 'staged': staged, 'actual': actual}

def seal_supervisor_limits(role_limits):
    target = role_limits['supervisor']
    for name, pair in target.items():
        current = resource.getrlimit(getattr(resource, name))
        if current[1] != resource.RLIM_INFINITY and pair[1] > current[1]:
            raise LimitOrderError('STOP_FINAL_WOULD_RAISE_HARD:' + name)
    for name, pair in target.items():
        resource.setrlimit(getattr(resource, name), tuple(pair))
    actual = {name: list(resource.getrlimit(getattr(resource, name))) for name in target}
    if actual != target:
        raise LimitOrderError('STOP_FINAL_EFFECTIVE_LIMITS')
    return actual

