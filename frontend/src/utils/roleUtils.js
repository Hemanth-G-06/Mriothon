/**
 * Normalize and identify user role from backend API responses,
 * token payloads, user objects, or Django group memberships.
 *
 * Supported operational roles:
 * - 'admin'
 * - 'engineer'
 * - 'supervisor'
 *
 * Returns null if role is missing or invalid.
 * NEVER defaults silently to 'engineer'.
 *
 * @param {Object|string} userObjOrRole
 * @param {Object} [fallbackObj]
 * @returns {'admin'|'engineer'|'supervisor'|null}
 */
export function normalizeUserRole(userObjOrRole, fallbackObj = {}) {
  if (!userObjOrRole && !fallbackObj) return null;

  // 1. If a string was passed directly
  if (typeof userObjOrRole === 'string') {
    const directLower = userObjOrRole.trim().toLowerCase();
    if (directLower === 'admin' || directLower === 'administrator' || directLower.includes('admin')) {
      return 'admin';
    }
    if (directLower === 'supervisor' || directLower.includes('super')) {
      return 'supervisor';
    }
    if (directLower === 'engineer' || directLower.includes('eng')) {
      return 'engineer';
    }
  }

  const merged = {
    ...fallbackObj,
    ...(typeof userObjOrRole === 'object' && userObjOrRole !== null ? userObjOrRole : {})
  };

  // 2. Direct property candidates
  const candidate =
    merged.role ||
    merged.user_role ||
    merged.user_type ||
    merged.role_name ||
    merged.type ||
    (merged.user && (merged.user.role || merged.user.user_type || merged.user.role_name));

  if (typeof candidate === 'string') {
    const lower = candidate.trim().toLowerCase();
    if (lower === 'admin' || lower === 'administrator' || lower.includes('admin')) {
      return 'admin';
    }
    if (lower === 'supervisor' || lower.includes('super')) {
      return 'supervisor';
    }
    if (lower === 'engineer' || lower.includes('eng')) {
      return 'engineer';
    }
  }

  // 3. Django Groups list (e.g. ['Admin'], ['Supervisor'], [{ name: 'Engineer' }])
  const groups = merged.groups || (merged.user && merged.user.groups);
  if (Array.isArray(groups) && groups.length > 0) {
    const firstGroup = typeof groups[0] === 'string' ? groups[0].toLowerCase() : (groups[0]?.name || '').toLowerCase();
    if (firstGroup.includes('admin')) return 'admin';
    if (firstGroup.includes('super')) return 'supervisor';
    if (firstGroup.includes('eng')) return 'engineer';
  } else if (typeof merged.group === 'string') {
    const groupLower = merged.group.toLowerCase();
    if (groupLower.includes('admin')) return 'admin';
    if (groupLower.includes('super')) return 'supervisor';
    if (groupLower.includes('eng')) return 'engineer';
  }

  // 4. Django is_superuser / is_staff flags
  if (merged.is_superuser === true || (merged.user && merged.user.is_superuser === true)) {
    return 'admin';
  }
  if (merged.is_staff === true || (merged.user && merged.user.is_staff === true)) {
    return 'admin';
  }

  // 5. Check email or username for known demo / seed user patterns
  const identifier = (merged.email || merged.username || '').toLowerCase();
  if (identifier.includes('admin') || identifier.includes('sarah.connor')) {
    return 'admin';
  }
  if (identifier.includes('super') || identifier.includes('marcus.brody')) {
    return 'supervisor';
  }
  if (identifier.includes('engineer') || identifier.includes('alex.vance')) {
    return 'engineer';
  }

  // Do NOT default silently to engineer
  return null;
}
