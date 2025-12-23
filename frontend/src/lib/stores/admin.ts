/**
 * Admin Store - State management for Admin Portal
 * 
 * Handles:
 * - Users list with loading/error states
 * - Selected user for detail view
 * - Audit log entries
 * - CRUD operations
 */

import { writable, derived, get } from 'svelte/store';
import { auth } from './auth';

// =============================================================================
// TYPES
// =============================================================================

export interface AdminUser {
    id: string;
    email: string;
    display_name: string | null;
    employee_id: string | null;
    department_access: string[];     // Departments they can query
    dept_head_for: string[];         // Departments they can grant access to
    is_super_user: boolean;
    is_active: boolean;
    last_login_at: string | null;
    // Computed role for display (derived from is_super_user and dept_head_for)
    role?: 'user' | 'dept_head' | 'super_user';
}

export interface UserDetail extends AdminUser {
    tier: string;
    departments: DepartmentAccess[];
}

export interface DepartmentAccess {
    slug: string;
    name: string;
    access_level: string;
    is_dept_head: boolean;
    granted_at: string | null;
}

export interface Department {
    id: string;
    slug: string;
    name: string;
    description?: string;
    user_count?: number;
}

export interface AuditEntry {
    id: string;
    action: string;
    actor_email: string | null;
    target_email: string | null;
    department_slug: string | null;
    old_value: string | null;
    new_value: string | null;
    reason: string | null;
    created_at: string;
    ip_address: string | null;
}

export interface AdminStats {
    total_users: number;
    users_by_role: Record<string, number>;
    users_by_department: Department[];
    recent_logins_7d: number;
    recent_access_changes_7d: number;
}

// =============================================================================
// HELPERS
// =============================================================================

/**
 * Compute display role from user properties
 * Super users > Dept heads > Regular users
 */
export function getDisplayRole(user: AdminUser): 'super_user' | 'dept_head' | 'user' {
    if (user.is_super_user) return 'super_user';
    if (user.dept_head_for && user.dept_head_for.length > 0) return 'dept_head';
    return 'user';
}

/**
 * Get role label for display
 */
export function getRoleLabel(role: string): string {
    switch (role) {
        case 'super_user': return 'Super User';
        case 'dept_head': return 'Dept Head';
        default: return 'User';
    }
}

/**
 * Valid department slugs (static list since we don't have a departments table)
 */
export const VALID_DEPARTMENTS = [
    { slug: 'sales', name: 'Sales' },
    { slug: 'purchasing', name: 'Purchasing' },
    { slug: 'warehouse', name: 'Warehouse' },
    { slug: 'credit', name: 'Credit' },
    { slug: 'accounting', name: 'Accounting' },
    { slug: 'it', name: 'IT' },
];

interface AdminState {
    // Users
    users: AdminUser[];
    usersLoading: boolean;
    usersError: string | null;
    
    // Selected user detail
    selectedUser: UserDetail | null;
    selectedUserLoading: boolean;
    
    // Departments
    departments: Department[];
    departmentsLoading: boolean;
    
    // Audit log
    auditEntries: AuditEntry[];
    auditTotal: number;
    auditLoading: boolean;
    auditOffset: number;
    
    // Stats
    stats: AdminStats | null;
    statsLoading: boolean;
    
    // Filters
    departmentFilter: string | null;
    searchQuery: string;
    auditActionFilter: string | null;
}

// =============================================================================
// INITIAL STATE
// =============================================================================

const initialState: AdminState = {
    users: [],
    usersLoading: false,
    usersError: null,
    
    selectedUser: null,
    selectedUserLoading: false,
    
    departments: [],
    departmentsLoading: false,
    
    auditEntries: [],
    auditTotal: 0,
    auditLoading: false,
    auditOffset: 0,
    
    stats: null,
    statsLoading: false,
    
    departmentFilter: null,
    searchQuery: '',
    auditActionFilter: null,
};

// =============================================================================
// STORE
// =============================================================================

function createAdminStore() {
    const { subscribe, set, update } = writable<AdminState>(initialState);
    
    function getApiBase(): string {
        return import.meta.env.VITE_API_URL || 'http://localhost:8000';
    }
    
    function getHeaders(): Record<string, string> {
        const email = auth.getEmail();
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
        };
        if (email) {
            headers['X-User-Email'] = email;
        }
        return headers;
    }
    
    async function apiCall<T>(
        path: string,
        options: RequestInit = {}
    ): Promise<{ success: boolean; data?: T; error?: string }> {
        try {
            const res = await fetch(`${getApiBase()}${path}`, {
                ...options,
                headers: {
                    ...getHeaders(),
                    ...(options.headers || {}),
                },
            });
            
            const json = await res.json();
            
            if (!res.ok) {
                return {
                    success: false,
                    error: json.detail || json.error || `HTTP ${res.status}`,
                };
            }
            
            return json;
        } catch (e) {
            console.error('[AdminStore] API error:', e);
            return {
                success: false,
                error: e instanceof Error ? e.message : 'Network error',
            };
        }
    }
    
    return {
        subscribe,
        
        // =====================================================================
        // USERS
        // =====================================================================
        
        async loadUsers(department?: string, search?: string) {
            update(s => ({ ...s, usersLoading: true, usersError: null }));
            
            const params = new URLSearchParams();
            if (department) params.set('department', department);
            if (search) params.set('search', search);
            
            const queryString = params.toString();
            const path = `/api/admin/users${queryString ? `?${queryString}` : ''}`;
            
            const result = await apiCall<{ users: AdminUser[]; count: number }>(path);
            
            if (result.success && result.data) {
                update(s => ({
                    ...s,
                    users: result.data!.users,
                    usersLoading: false,
                }));
            } else {
                update(s => ({
                    ...s,
                    usersLoading: false,
                    usersError: result.error || 'Failed to load users',
                }));
            }
        },
        
        async loadUserDetail(userId: string) {
            update(s => ({ ...s, selectedUserLoading: true }));
            
            const result = await apiCall<{ user: UserDetail }>(`/api/admin/users/${userId}`);
            
            if (result.success && result.data) {
                update(s => ({
                    ...s,
                    selectedUser: result.data!.user,
                    selectedUserLoading: false,
                }));
            } else {
                update(s => ({
                    ...s,
                    selectedUser: null,
                    selectedUserLoading: false,
                }));
            }
        },
        
        clearSelectedUser() {
            update(s => ({ ...s, selectedUser: null }));
        },
        
        // =====================================================================
        // ROLE MANAGEMENT
        // =====================================================================
        
        async changeUserRole(
            userId: string,
            newRole: string,
            reason?: string
        ): Promise<{ success: boolean; error?: string }> {
            const result = await apiCall<{ message: string }>(
                `/api/admin/users/${userId}/role`,
                {
                    method: 'PUT',
                    body: JSON.stringify({ new_role: newRole, reason }),
                }
            );
            
            if (result.success) {
                // Refresh the user list and detail
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);
                if (state.selectedUser?.id === userId) {
                    await this.loadUserDetail(userId);
                }
            }
            
            return result;
        },
        
        // =====================================================================
        // ACCESS CONTROL
        // =====================================================================
        
        async grantAccess(
            userId: string,
            departmentSlug: string,
            accessLevel: string = 'read',
            makeDeptHead: boolean = false,
            reason?: string
        ): Promise<{ success: boolean; error?: string }> {
            const result = await apiCall<{ message: string }>(
                '/api/admin/access/grant',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        user_id: userId,
                        department_slug: departmentSlug,
                        access_level: accessLevel,
                        make_dept_head: makeDeptHead,
                        reason,
                    }),
                }
            );
            
            if (result.success) {
                // Refresh user detail
                await this.loadUserDetail(userId);
            }
            
            return result;
        },
        
        async revokeAccess(
            userId: string,
            departmentSlug: string,
            reason?: string
        ): Promise<{ success: boolean; error?: string }> {
            const result = await apiCall<{ message: string }>(
                '/api/admin/access/revoke',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        user_id: userId,
                        department_slug: departmentSlug,
                        reason,
                    }),
                }
            );

            if (result.success) {
                // Refresh user detail
                await this.loadUserDetail(userId);
            }

            return result;
        },

        // =====================================================================
        // DEPT HEAD MANAGEMENT (Super User Only)
        // =====================================================================

        async promoteToDeptHead(
            targetEmail: string,
            department: string
        ): Promise<{ success: boolean; error?: string }> {
            const result = await apiCall<{ message: string }>(
                '/api/admin/dept-head/promote',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        target_email: targetEmail,
                        department,
                    }),
                }
            );

            if (result.success) {
                // Refresh users list
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);
            }

            return result;
        },

        async revokeDeptHead(
            targetEmail: string,
            department: string
        ): Promise<{ success: boolean; error?: string }> {
            const result = await apiCall<{ message: string }>(
                '/api/admin/dept-head/revoke',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        target_email: targetEmail,
                        department,
                    }),
                }
            );

            if (result.success) {
                // Refresh users list
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);
            }

            return result;
        },

        // =====================================================================
        // SUPER USER MANAGEMENT (Super User Only)
        // =====================================================================

        async promoteToSuperUser(
            targetEmail: string
        ): Promise<{ success: boolean; error?: string }> {
            const result = await apiCall<{ message: string }>(
                '/api/admin/super-user/promote',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        target_email: targetEmail,
                    }),
                }
            );

            if (result.success) {
                // Refresh users list
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);
            }

            return result;
        },

        async revokeSuperUser(
            targetEmail: string
        ): Promise<{ success: boolean; error?: string }> {
            const result = await apiCall<{ message: string }>(
                '/api/admin/super-user/revoke',
                {
                    method: 'POST',
                    body: JSON.stringify({
                        target_email: targetEmail,
                    }),
                }
            );

            if (result.success) {
                // Refresh users list
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);
            }

            return result;
        },

        // =====================================================================
        // USER CRUD
        // =====================================================================

        async createUser(data: {
            email: string;
            display_name?: string;
            employee_id?: string;
            role?: string;
            primary_department?: string;
            department_access?: string[];
            reason?: string;
        }): Promise<{ success: boolean; data?: any; error?: string }> {
            const result = await apiCall<{ user: AdminUser; message: string }>(
                '/api/admin/users',
                {
                    method: 'POST',
                    body: JSON.stringify(data),
                }
            );

            if (result.success) {
                // Refresh users list
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);
            }

            return result;
        },

        async batchCreateUsers(data: {
            users: Array<{ email: string; display_name?: string; department?: string }>;
            default_department?: string;
            reason?: string;
        }): Promise<{
            success: boolean;
            data?: {
                created: string[];
                created_count: number;
                already_existed: string[];
                already_existed_count: number;
                failed: Array<{ email: string; error: string }>;
                failed_count: number;
                message: string;
            };
            error?: string
        }> {
            const result = await apiCall<any>(
                '/api/admin/users/batch',
                {
                    method: 'POST',
                    body: JSON.stringify(data),
                }
            );

            if (result.success) {
                // Refresh users list
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);
            }

            return result;
        },

        async updateUser(
            userId: string,
            data: {
                email?: string;
                display_name?: string;
                employee_id?: string;
                primary_department?: string;
                reason?: string;
            }
        ): Promise<{ success: boolean; data?: any; error?: string }> {
            const result = await apiCall<{ user: AdminUser; message: string }>(
                `/api/admin/users/${userId}`,
                {
                    method: 'PUT',
                    body: JSON.stringify(data),
                }
            );

            if (result.success) {
                // Refresh users list and detail
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);
                if (state.selectedUser?.id === userId) {
                    await this.loadUserDetail(userId);
                }
            }

            return result;
        },

        async deactivateUser(
            userId: string,
            reason?: string
        ): Promise<{ success: boolean; error?: string }> {
            const result = await apiCall<{ message: string }>(
                `/api/admin/users/${userId}`,
                {
                    method: 'DELETE',
                    body: JSON.stringify({ reason }),
                }
            );

            if (result.success) {
                // Refresh users list
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);

                // Clear selected user if it was the deactivated one
                if (state.selectedUser?.id === userId) {
                    update(s => ({ ...s, selectedUser: null }));
                }
            }

            return result;
        },

        async reactivateUser(
            userId: string,
            reason?: string
        ): Promise<{ success: boolean; data?: any; error?: string }> {
            const params = reason ? `?reason=${encodeURIComponent(reason)}` : '';

            const result = await apiCall<{ user: AdminUser; message: string }>(
                `/api/admin/users/${userId}/reactivate${params}`,
                {
                    method: 'POST',
                }
            );

            if (result.success) {
                // Refresh users list
                const state = get({ subscribe });
                await this.loadUsers(state.departmentFilter || undefined);
            }

            return result;
        },

        // =====================================================================
        // DEPARTMENTS
        // =====================================================================
        
        async loadDepartments() {
            update(s => ({ ...s, departmentsLoading: true }));
            
            const result = await apiCall<{ departments: Department[] }>('/api/admin/departments');
            
            if (result.success && result.data) {
                update(s => ({
                    ...s,
                    departments: result.data!.departments,
                    departmentsLoading: false,
                }));
            } else {
                update(s => ({ ...s, departmentsLoading: false }));
            }
        },
        
        // =====================================================================
        // AUDIT LOG
        // =====================================================================
        
        async loadAuditLog(
            options: {
                action?: string;
                targetEmail?: string;
                department?: string;
                limit?: number;
                offset?: number;
            } = {}
        ) {
            update(s => ({ ...s, auditLoading: true }));
            
            const params = new URLSearchParams();
            if (options.action) params.set('action', options.action);
            if (options.targetEmail) params.set('target_email', options.targetEmail);
            if (options.department) params.set('department', options.department);
            params.set('limit', String(options.limit || 50));
            params.set('offset', String(options.offset || 0));
            
            const result = await apiCall<{
                entries: AuditEntry[];
                total: number;
                has_more: boolean;
            }>(`/api/admin/audit?${params.toString()}`);
            
            if (result.success && result.data) {
                update(s => ({
                    ...s,
                    auditEntries: result.data!.entries,
                    auditTotal: result.data!.total,
                    auditOffset: options.offset || 0,
                    auditLoading: false,
                }));
            } else {
                update(s => ({ ...s, auditLoading: false }));
            }
        },
        
        // =====================================================================
        // STATS
        // =====================================================================
        
        async loadStats() {
            update(s => ({ ...s, statsLoading: true }));
            
            const result = await apiCall<AdminStats>('/api/admin/stats');
            
            if (result.success && result.data) {
                update(s => ({
                    ...s,
                    stats: result.data!,
                    statsLoading: false,
                }));
            } else {
                update(s => ({ ...s, statsLoading: false }));
            }
        },
        
        // =====================================================================
        // FILTERS
        // =====================================================================
        
        setDepartmentFilter(slug: string | null) {
            update(s => ({ ...s, departmentFilter: slug }));
        },
        
        setSearchQuery(query: string) {
            update(s => ({ ...s, searchQuery: query }));
        },
        
        setAuditActionFilter(action: string | null) {
            update(s => ({ ...s, auditActionFilter: action }));
        },
        
        // =====================================================================
        // RESET
        // =====================================================================
        
        reset() {
            set(initialState);
        },
    };
}

export const adminStore = createAdminStore();

// =============================================================================
// DERIVED STORES
// =============================================================================

export const adminUsers = derived(adminStore, $s => $s.users);
export const adminUsersLoading = derived(adminStore, $s => $s.usersLoading);
export const adminUsersError = derived(adminStore, $s => $s.usersError);

export const selectedUser = derived(adminStore, $s => $s.selectedUser);
export const selectedUserLoading = derived(adminStore, $s => $s.selectedUserLoading);

export const adminDepartments = derived(adminStore, $s => $s.departments);
export const adminDepartmentsLoading = derived(adminStore, $s => $s.departmentsLoading);

export const auditEntries = derived(adminStore, $s => $s.auditEntries);
export const auditTotal = derived(adminStore, $s => $s.auditTotal);
export const auditLoading = derived(adminStore, $s => $s.auditLoading);

export const adminStats = derived(adminStore, $s => $s.stats);
export const adminStatsLoading = derived(adminStore, $s => $s.statsLoading);

export const departmentFilter = derived(adminStore, $s => $s.departmentFilter);
export const searchQuery = derived(adminStore, $s => $s.searchQuery);

// Filtered users based on search
export const filteredUsers = derived(
    [adminStore],
    ([$s]) => {
        if (!$s.searchQuery) return $s.users;
        
        const q = $s.searchQuery.toLowerCase();
        return $s.users.filter(u =>
            u.email.toLowerCase().includes(q) ||
            (u.display_name || '').toLowerCase().includes(q) ||
            (u.employee_id || '').toLowerCase().includes(q)
        );
    }
);