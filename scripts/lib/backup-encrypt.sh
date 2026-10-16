#!/bin/bash
# EVA-006 stage 1 (ADR-007 S3): encrypt the off-site backup archive with age
# before it leaves the server. Only the PUBLIC recipient key is on the server;
# the private key stays offline with the owner (runbook:
# docs/operations/BACKUP_ENCRYPTION_RUNBOOK.md).
#
#   BACKUP_AGE_RECIPIENT        age public key ("age1…"); empty = no encryption
#   BACKUP_REQUIRE_ENCRYPTION   "true" = refuse to upload unencrypted (activation switch)

# encrypt_archive <plain archive> <encrypted output>  → 0 ok, non-zero = do not upload
encrypt_archive() {
  local plain="$1" out="$2"
  local recipient="${BACKUP_AGE_RECIPIENT:-}"
  if [ -z "${recipient}" ]; then
    echo "encrypt_archive: BACKUP_AGE_RECIPIENT is not set" >&2
    return 3
  fi
  case "${recipient}" in
    age1*) ;;
    *) echo "encrypt_archive: BACKUP_AGE_RECIPIENT is not an age public key" >&2; return 4 ;;
  esac
  command -v age >/dev/null 2>&1 || { echo "encrypt_archive: age is not installed" >&2; return 5; }
  rm -f "${out}"
  age --encrypt -r "${recipient}" -o "${out}" "${plain}" || { rm -f "${out}"; return 6; }
  # Plausibility: age header present and output at least as large as the input.
  if ! head -c 21 "${out}" | grep -q "age-encryption.org/v1"; then
    rm -f "${out}"; echo "encrypt_archive: output has no age header" >&2; return 7
  fi
  if [ "$(wc -c < "${out}")" -lt "$(wc -c < "${plain}")" ]; then
    rm -f "${out}"; echo "encrypt_archive: output smaller than input" >&2; return 8
  fi
  return 0
}

# select_upload_file <plain archive>  → prints the file to upload, non-zero = abort
select_upload_file() {
  local plain="$1"
  if [ -n "${BACKUP_AGE_RECIPIENT:-}" ]; then
    encrypt_archive "${plain}" "${plain}.age" || return $?
    printf '%s\n' "${plain}.age"
    return 0
  fi
  if [ "${BACKUP_REQUIRE_ENCRYPTION:-false}" = "true" ]; then
    echo "select_upload_file: encryption required but BACKUP_AGE_RECIPIENT is not set" >&2
    return 9
  fi
  echo "WARNING: uploading an UNENCRYPTED backup (BACKUP_AGE_RECIPIENT not set; ADR-007 S3)" >&2
  printf '%s\n' "${plain}"
}
