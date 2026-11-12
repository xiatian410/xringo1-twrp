/* Query a compiled recovery policy using the same libsepol built by AOSP.
 * This is an offline decision check, not a mock and not a policy load into
 * the host kernel. Exit 2 means the permission does not exist in the policy.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sepol/policydb/services.h>

int main(int argc, char **argv) {
    if (argc != 6) return 64;
    FILE *f = fopen(argv[1], "rb");
    if (!f || fseek(f, 0, SEEK_END)) return 65;
    long size = ftell(f);
    if (size <= 0 || fseek(f, 0, SEEK_SET)) return 65;
    void *bytes = malloc(size);
    if (!bytes || fread(bytes, 1, size, f) != (size_t)size) return 65;
    fclose(f);
    policydb_t policy;
    if (policydb_init(&policy) || sepol_set_policydb(&policy) ||
        sepol_load_policy(bytes, size)) return 66;
    free(bytes);
    type_datum_t *helper = hashtab_search(policy.p_types.table, "dijun_usb");
    if (!helper) return 69;
    printf("DOMAIN dijun_usb %s\n",
           ebitmap_get_bit(&policy.permissive_map, helper->s.value)
               ? "permissive" : "enforcing");
    sepol_security_class_t cls;
    sepol_access_vector_t perm;
    if (sepol_string_to_security_class(argv[4], &cls) ||
        sepol_string_to_av_perm(cls, argv[5], &perm)) {
        printf("MISSING permission %s:%s\n", argv[4], argv[5]);
        return 2;
    }
    sepol_security_id_t src, dst;
    if (sepol_context_to_sid(argv[2], strlen(argv[2]) + 1, &src) ||
        sepol_context_to_sid(argv[3], strlen(argv[3]) + 1, &dst)) return 67;
    struct sepol_av_decision avd;
    if (sepol_compute_av(src, dst, cls, perm, &avd)) return 68;
    int allowed = (avd.allowed & perm) == perm;
    printf("%s %s -> %s %s:%s\n", allowed ? "ALLOW" : "DENY",
           argv[2], argv[3], argv[4], argv[5]);
    return allowed ? 0 : 1;
}
