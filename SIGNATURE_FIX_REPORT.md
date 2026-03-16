# Signature Consistency Fix Report

## Purpose

This document is a handoff for another agent working on a different branch.

The goal is to verify and preserve the intended behavior of the PHP <-> Python signing flow, especially for document closing/protocolization, and to prevent partial success states such as:

- signed PDF saved to disk
- task closed/unlocked
- but document not protocolized
- or document state/number/date left inconsistent

The desired outcome is:

- DB state is the source of truth
- the signing/closing operation is transactionally consistent from the PHP system point of view
- if the close-sign process fails, the user can retry
- the PDF file may remain on disk, but PHP must not interpret file presence as successful completion

## Summary of Issues Found

### Issue 1: Shared DB connection between concurrent requests

Observed symptom:

- concurrent requests could fail with `psycopg2.InterfaceError: connection already closed`

Root cause:

- `firmar_python/app/utils/db.py` used a shared/global `conn`
- one request could close the connection while another request still expected to use it

Effect:

- random failures under concurrent signing load
- especially visible during protocolization/close PDF flow

### Issue 2: Non-atomic close-sign flow

Observed symptom:

- the document could be signed and saved
- the task could be finalized/unlocked
- but protocolization could be missing or inconsistent
- user ends up with a document that looks processed in one subsystem but is not correctly reflected in DB state/number/date

Root cause:

- the Python flow committed protocolization and task-finalization in separate DB operations
- the file save was outside the same transaction boundary
- failure in a later step could leave the systems out of sync

Effect:

- inconsistent state between PHP expectations, Python processing, and DB
- user may be blocked from retrying correctly

## Desired Behavior

For close-sign operations, the branch must behave as follows:

1. Generate the signed PDF content.
2. Protocolize the document and prepare the close fields.
3. Finalize/unlock the task.
4. Save the signed PDF file.
5. Only after all of the above succeed, commit the DB transaction.

If any step fails:

1. Roll back the DB transaction.
2. Leave the document/task state in a retryable condition.
3. Do not rely on the saved file to represent success.
4. Preserve the file if it was already written.

Important rule:

- DB state and task state are the source of truth.
- File existence is not the source of truth.

## Files Already Fixed in This Branch

The current branch changed these files:

- `firmar_python/app/utils/db.py`
- `firmar_python/app/services/signatures_service.py`
- `firmar_python/tests/test_db_utils.py`

The current merged code also preserves branch-specific behavior for:

- project-specific protocolization/finalization helpers
- Redis-backed signing context handling for digital signatures
- certificate expiration validation before digital signing/finalization
- `signature_pdf_loro()` flow

## What Changed in This Branch

### 1. DB helpers no longer share a global connection

In `firmar_python/app/utils/db.py`:

- added `open_db_connection()`
- removed the shared-connection behavior from the signing helpers
- each helper can now either:
  - open/own its own connection, or
  - reuse a caller-provided connection

Relevant helper signatures:

- `get_number_and_date_then_close(pdf_to_close, id_doc, conn=None, commit=True)`
- `unlock_pdf_and_close_task(params, conn=None, commit=True)`
- `get_number_and_date_then_close_project(pdf_to_close, id_doc, conn=None, commit=True)`
- `unlock_pdf_and_close_task_project(params, conn=None, commit=True)`

This allows the service layer to group multiple DB actions in a single transaction.

### 2. The service layer now owns the transaction for close-sign flows

In `firmar_python/app/services/signatures_service.py`:

- the non-digital close flow uses one DB transaction for:
  - protocolization
  - task finalization/unlock
  - final commit after file save
- the digital close-finalization flow follows the same approach
- the same transactional rule was extended to project-specific protocolization/finalization paths
- digital flows still preserve the Redis signing-context behavior from the other branch

The transaction is committed only after:

- protocolization succeeded
- task finalization succeeded
- the signed file was saved successfully

If any of those fail:

- the DB transaction is rolled back
- the file is preserved
- the operation returns an error

### 3. File is preserved on rollback

Per the required behavior:

- rollback does **not** delete the saved file
- this is intentional
- the file may exist even if the DB transaction failed

Therefore the other branch must also enforce:

- PHP must not treat file existence as proof of successful signature completion

### 4. Tests were added

In `firmar_python/tests/test_db_utils.py`:

- connection independence is tested
- rollback on PDF-close failure is tested
- support for caller-owned connection with `commit=False` is tested
- backward-compatible handling of `is_signed` defaulting is preserved in the DB helper layer

## How to Fix on the Other Branch

The other agent should implement the fix in this order.

### Step A: Fix connection handling in `db.py`

Do this first.

Required changes:

- add a helper like `open_db_connection()`
- stop using any shared/global `conn`
- make these functions accept an optional existing connection:
  - `get_number_and_date_then_close(..., conn=None, commit=True)`
  - `unlock_pdf_and_close_task(..., conn=None, commit=True)`
  - `get_number_and_date_then_close_project(..., conn=None, commit=True)` if the branch has project support
  - `unlock_pdf_and_close_task_project(..., conn=None, commit=True)` if the branch has project support

Expected behavior:

- if no connection is provided, the helper opens and closes its own connection
- if a connection is provided, the helper uses it
- if `commit=False`, the helper must not commit
- if a failure happens, it must rollback

### Step B: Make the service own the transaction

Do this second.

In `firmar_python/app/services/signatures_service.py`:

- open one transaction connection for the close-sign path
- call protocolization with that connection
- call task finalization with that same connection
- save the PDF file
- commit only after all of that succeeds

If the branch contains project support, apply the same rule to:

- project protocolization
- project finalization/unlock

Expected behavior:

- no intermediate commit before the file is saved
- no separate transaction for protocolization and finalization

### Step C: Keep rollback DB-only, not filesystem cleanup

Do this third.

If the transaction fails:

- rollback the DB transaction
- return an error
- preserve the file if it was already written

Do **not** delete the file on rollback.

### Step D: Verify PHP behavior

Do this fourth.

The PHP branch must treat:

- DB state
- task state
- Python success response

as the indicators of success.

The PHP branch must **not** treat:

- file existence on disk

as proof that the operation completed successfully.

### Step E: Run the verification scenarios

Do this last.

Minimum verification:

- one successful close-sign
- one forced failure before commit
- one concurrent run with at least two requests

If any of these fail, do not ship.

## Step-by-Step Instructions for the Agent on the Other Branch

### Step 1: Inspect the target branch before changing anything

Check whether the target branch contains local modifications or feature changes in:

- `firmar_python/app/utils/db.py`
- `firmar_python/app/services/signatures_service.py`
- any PHP code calling `firmalote` / `firmaloteend`
- any Redis/signing-context integration for digital signatures
- any project-specific flows
- any SQL function name changes such as:
  - `f_documento_protocolizar`
  - `f_finalizar_proceso_firmado_v2`
  - `f_proyecto_protocolizar`
  - `f_proyecto_finalizar_proceso_firmado_v2`

If those APIs differ, adapt the fix instead of blindly copying code.

### Step 2: Verify whether `db.py` still uses shared/global connection state

Search for:

- `global conn`
- module-level `conn`
- reuse of a connection across requests

If found, replace that approach with:

- `open_db_connection()`
- local per-operation connections
- optional caller-owned connection injection

Required result:

- `get_number_and_date_then_close(...)` must support a provided connection
- `unlock_pdf_and_close_task(...)` must support a provided connection
- project equivalents must also support a provided connection if they exist

### Step 3: Verify the service flow is transactional

Inspect `SignaturesService.init_signature_pdf()` and `SignaturesService.end_signature_pdf()`.

For close-sign cases, verify the branch does **not** do this:

1. commit protocolization
2. commit task finalization
3. save file later

That behavior is incorrect.

The correct flow is:

1. open a DB transaction
2. protocolize using the shared transaction
3. finalize/unlock task using the same transaction
4. save file
5. commit once at the end

If the branch has project-specific helpers, the same sequence must apply there too.

### Step 4: Verify rollback behavior

If any of these fail:

- protocolization
- PDF close field update
- finalization/unlock call
- file save
- DB commit

Then the branch must:

- rollback the transaction
- return an error
- leave the task/document state retryable

Do **not** delete the file during rollback.

### Step 5: Verify PHP-side assumptions

Review the PHP code paths that call the Python signer.

At minimum, verify the PHP branch does not assume success from:

- presence of a file on disk
- partially returned PDF payload
- incomplete downstream side effects

PHP should treat success as meaning:

- Python returned success
- DB state reflects the correct state
- protocolization exists when the document should be closed

If the branch contains any code that uses file existence as proof of success, flag it and fix it.

### Step 6: Verify SQL behavior

The branch should preserve these semantics:

- protocolization assigns `numero`, `anio`, `fecha`, and the correct final document state when appropriate
- finalization marks signature/task completion without corrupting the protocolization outcome

Pay special attention to whether the SQL function used by Python can:

- overwrite `estado`
- leave `numero`/`fecha` unset
- mark the task complete when protocolization was not truly persisted

If the SQL on the target branch differs from this branch, review it carefully before shipping the fix.

### Step 7: Port or recreate the tests

Add or adapt tests covering:

- concurrent requests do not share a DB connection
- `get_number_and_date_then_close(..., conn=..., commit=False)` does not commit caller-owned transactions
- `unlock_pdf_and_close_task(..., conn=..., commit=False)` does not commit caller-owned transactions
- project helper equivalents, if present
- rollback happens on close-PDF failure

If the target branch cannot run the exact same test file, recreate equivalent tests.

## Concrete Verification Checklist

The other agent should verify all of the following:

- two concurrent close-sign requests no longer fail with `connection already closed`
- a close-sign failure does not leave the task finalized while protocolization is missing
- a close-sign failure does not leave the document in a non-retryable locked state
- the same guarantee holds for project-specific close-sign flows, if present
- successful close-sign still:
  - protocolizes the document
  - sets the correct number/date
  - finalizes/unlocks the task
  - saves the file
- failure after file write but before DB commit:
  - preserves the file
  - rolls back DB/task state
  - allows the user to retry

## Suggested Test Scenarios

### Scenario A: Normal non-digital closing signature

Expected result:

- document gets protocolized
- number/date are filled
- task is finalized
- file is saved
- response is success

### Scenario B: Failure during close PDF field injection

Force failure in the Java PDF update service.

Expected result:

- DB transaction rolls back
- task is not finalized as successful
- user can retry
- operation returns error

### Scenario C: Failure during file save

Force `save_signed_pdf()` to fail.

Expected result:

- DB transaction rolls back
- task is not finalized as successful
- user can retry
- operation returns error

### Scenario D: Concurrent close-sign requests

Run at least two simultaneous requests.

Expected result:

- no shared connection error
- no cross-request DB contamination

### Scenario E: File exists but DB rollback occurred

Simulate a failure after file write but before final commit.

Expected result:

- file may remain on disk
- PHP/DB must still treat the document as not successfully completed
- retry must still be possible

## Red Flags the Other Agent Must Watch For

- any `global conn`
- any implicit reuse of DB connection object across requests
- helper functions that auto-commit when they should participate in a larger transaction
- project-specific helper functions that still auto-commit or use global connection state
- logic that finalizes task state before file save but outside a shared transaction
- PHP logic that interprets filesystem state as final success
- SQL logic that can set final document state independently of protocolization persistence

## If the Other Branch Has Feature Divergence

If the target branch changed signing behavior, the agent should preserve the same transactional principle even if the exact code shape differs.

The principle is more important than line-by-line parity:

- one transaction for the DB portion of close-sign
- commit only after all required side effects succeed
- rollback on failure
- preserve file
- DB remains authoritative

## Acceptance Criteria

The fix is complete only if:

- the target branch no longer uses shared DB connection state in this flow
- close-sign operations are transactionally consistent
- a failed close-sign can be retried
- protocolization/task/document state cannot drift apart
- file preservation on rollback does not create false success in PHP
- tests or equivalent verification were executed and documented

## Reference for the Other Agent

Use this branch as the implementation reference for:

- `firmar_python/app/utils/db.py`
- `firmar_python/app/services/signatures_service.py`
- `firmar_python/tests/test_db_utils.py`

Pay special attention to preserving these merged features while porting the fix:

- Redis signing-context lifecycle for digital signatures
- project-specific protocolization/finalization helpers
- certificate expiration validation
- backward compatibility for callers that omit `is_signed`

If behavior on the target branch differs, adapt carefully rather than copying blindly.
