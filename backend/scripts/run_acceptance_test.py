#!/usr/bin/env python3
"""
End-to-End Acceptance Verification Script.
Executes the mandatory Round 2 workflow against the live running server:
- Real JWT Authentication (Admin, Engineer, Supervisor)
- Product Registration
- Single Image Inspection with genuine CV inference
- Celery & Redis Asynchronous Batch Inspection with fault isolation
- Engineer Scoped History vs Supervisor Global Queue
- Supervisor Confirm and Correct Reviews with immutability verification
- Server-side RBAC enforcement (Engineer 403 Forbidden on review)
"""

import sys
import time
import requests
from pathlib import Path

BASE_URL = "http://127.0.0.1:8000/api"
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent


def print_step(num, title):
    print(f"\n[STEP {num:02d}] {title}")


def run_acceptance():
    session = requests.Session()

    # -------------------------------------------------------------
    # Step 1: Health Check
    # -------------------------------------------------------------
    print_step(1, "Verify Django API Health")
    res = session.get(f"{BASE_URL}/health/")
    assert res.status_code == 200, f"Health check failed: {res.text}"
    print(f"✓ Health check response: {res.json()}")

    # -------------------------------------------------------------
    # Step 2: Login as Administrator
    # -------------------------------------------------------------
    print_step(2, "Login as Administrator (sarah.connor@gmail.com)")
    login_res = session.post(f"{BASE_URL}/auth/login/", json={
        "email": "sarah.connor@gmail.com",
        "password": "AdminPassword123!" if False else "Admin@123"
    })
    assert login_res.status_code == 200, f"Admin login failed: {login_res.text}"
    admin_tokens = login_res.json()
    admin_token = admin_tokens["access"]
    print(f"✓ Admin authenticated: {admin_tokens['user']['email']} (Role: {admin_tokens['user']['role']})")

    # -------------------------------------------------------------
    # Step 3: Register or Retrieve P-PLATE01
    # -------------------------------------------------------------
    print_step(3, "Ensure P-PLATE01 Product Registration as Admin")
    prod_res = session.get(f"{BASE_URL}/products/P-PLATE01/", headers={
        "Authorization": f"Bearer {admin_token}"
    })
    if prod_res.status_code == 404:
        reg_res = session.post(f"{BASE_URL}/products/", json={
            "id": "P-PLATE01",
            "name": "Demonstration metal plate",
            "model_version": "BIT-PLATE-CV-1.0",
            "description": "Synthetic centered plate with scratches or pits."
        }, headers={"Authorization": f"Bearer {admin_token}"})
        assert reg_res.status_code == 201, f"Failed to register product: {reg_res.text}"
        prod_data = reg_res.json()
    else:
        assert prod_res.status_code == 200, f"Error getting product: {prod_res.text}"
        prod_data = prod_res.json()
    print(f"✓ Product verified: {prod_data['id']} - {prod_data['name']} (Model: {prod_data['model_version']})")

    # -------------------------------------------------------------
    # Step 4: Login as Engineer
    # -------------------------------------------------------------
    print_step(4, "Login as Engineer (alex.vance@gmail.com)")
    eng_res = session.post(f"{BASE_URL}/auth/login/", json={
        "email": "alex.vance@gmail.com",
        "password": "Engineer@123"
    })
    assert eng_res.status_code == 200, f"Engineer login failed: {eng_res.text}"
    eng_tokens = eng_res.json()
    eng_token = eng_tokens["access"]
    print(f"✓ Engineer authenticated: {eng_tokens['user']['email']} (Role: {eng_tokens['user']['role']})")

    # -------------------------------------------------------------
    # Step 5: Engineer Uploads Single Valid Sample Image
    # -------------------------------------------------------------
    print_step(5, "Engineer Submits Single Image Inspection (inspection_001.png)")
    sample1_path = WORKSPACE_ROOT / "Samples" / "images" / "inspection_001.png"
    assert sample1_path.exists(), f"Sample 1 missing: {sample1_path}"

    with open(sample1_path, "rb") as f:
        single_res = session.post(
            f"{BASE_URL}/inspections/single/",
            data={"product_id": "P-PLATE01"},
            files={"file": ("inspection_001.png", f, "image/png")},
            headers={"Authorization": f"Bearer {eng_token}"}
        )
    assert single_res.status_code == 201, f"Single inspection failed: {single_res.text}"
    single_data = single_res.json()
    single_id = single_data["id"]

    print(f"✓ Single Inspection #{single_id} completed:")
    print(f"    - Predicted Class   : {single_data['predicted_class']}")
    print(f"    - Confidence        : {single_data['confidence']:.4f}")
    print(f"    - Defect Probability: {single_data['defect_probability']:.4f}")
    print(f"    - Model Version     : {single_data['model_version']}")
    print(f"    - Status            : {single_data['status']}")
    print(f"    - Image URL         : {single_data['image_url']}")

    assert single_data["predicted_class"] == "Defective"
    assert single_data["confidence"] == 1.0
    assert single_data["model_version"] == "BIT-PLATE-CV-1.0"
    assert single_data["status"] == "Completed"

    # -------------------------------------------------------------
    # Step 6: Engineer Submits Mixed Batch (Valid + Invalid)
    # -------------------------------------------------------------
    print_step(6, "Engineer Submits Mixed Batch (2 Valid Images + 2 Invalid Files)")
    sample2_path = WORKSPACE_ROOT / "Samples" / "images" / "inspection_002.jpg"
    sample3_path = WORKSPACE_ROOT / "Samples" / "images" / "inspection_003.png"
    invalid1_path = WORKSPACE_ROOT / "Validation" / "not_an_image.jpg"
    invalid2_path = WORKSPACE_ROOT / "Validation" / "too_small.png"

    with open(sample2_path, "rb") as f2, \
         open(sample3_path, "rb") as f3, \
         open(invalid1_path, "rb") as fi1, \
         open(invalid2_path, "rb") as fi2:

        batch_files = [
            ("files", ("inspection_002.jpg", f2, "image/jpeg")),
            ("files", ("inspection_003.png", f3, "image/png")),
            ("files", ("not_an_image.jpg", fi1, "image/jpeg")),
            ("files", ("too_small.png", fi2, "image/png")),
        ]

        batch_res = session.post(
            f"{BASE_URL}/inspections/batch/",
            data={"product_id": "P-PLATE01"},
            files=batch_files,
            headers={"Authorization": f"Bearer {eng_token}"}
        )

    assert batch_res.status_code == 201, f"Batch upload failed: {batch_res.text}"
    batch_init = batch_res.json()
    batch_id = batch_init["batch_id"]
    print(f"✓ Batch created: {batch_id}")
    print(f"    - Total Images : {batch_init['total']}")
    print(f"    - Queued Tasks : {batch_init['queued']}")
    print(f"    - Failed Inputs: {batch_init['failed']}")

    assert batch_init["total"] == 4
    assert batch_init["queued"] == 2
    assert batch_init["failed"] == 2

    # -------------------------------------------------------------
    # Step 7: Poll Batch Status until Celery Finishes
    # -------------------------------------------------------------
    print_step(7, "Poll Celery Batch Progress via Redis")
    final_batch = None
    for attempt in range(15):
        poll_res = session.get(f"{BASE_URL}/inspections/batch/{batch_id}/", headers={
            "Authorization": f"Bearer {eng_token}"
        })
        assert poll_res.status_code == 200, f"Batch poll failed: {poll_res.text}"
        batch_state = poll_res.json()
        print(f"    [Poll {attempt+1}] Status: {batch_state['status']} | Completed: {batch_state['completed']} | Failed: {batch_state['failed']} | Processing: {batch_state['processing']} | Queued: {batch_state['queued']}")

        if batch_state["completed"] + batch_state["failed"] >= batch_state["total"]:
            final_batch = batch_state
            break
        time.sleep(1.0)

    assert final_batch is not None, "Batch polling timed out!"
    print(f"✓ Celery Batch {batch_id} fully finished:")
    print(f"    - Completed: {final_batch['completed']}")
    print(f"    - Failed   : {final_batch['failed']}")

    # Check items isolation
    items = final_batch["items"]
    corrupt_item = next(it for it in items if it["file_name"] == "not_an_image.jpg")
    small_item = next(it for it in items if it["file_name"] == "too_small.png")
    valid_item2 = next(it for it in items if it["file_name"] == "inspection_002.jpg")
    valid_item3 = next(it for it in items if it["file_name"] == "inspection_003.png")

    assert corrupt_item["status"] == "Failed"
    assert corrupt_item["predicted_class"] == ""
    assert corrupt_item["confidence"] is None
    assert "cannot identify image file" in corrupt_item["failure_reason"]

    assert small_item["status"] == "Failed"
    assert small_item["predicted_class"] == ""
    assert "below the minimum required" in small_item["failure_reason"]

    assert valid_item2["status"] == "Completed"
    assert valid_item2["predicted_class"] == "Normal"
    assert valid_item2["confidence"] > 0.90

    assert valid_item3["status"] == "Completed"
    assert valid_item3["predicted_class"] == "Defective"
    assert valid_item3["confidence"] == 1.0

    print("✓ Fault Isolation verified: Invalid items recorded with failure reasons; valid items scored successfully.")

    # -------------------------------------------------------------
    # Step 8: Verify Engineer Scoped History
    # -------------------------------------------------------------
    print_step(8, "Verify Engineer Scoped History (/api/inspections/)")
    eng_hist_res = session.get(f"{BASE_URL}/inspections/", headers={
        "Authorization": f"Bearer {eng_token}"
    })
    assert eng_hist_res.status_code == 200, f"History fetch failed: {eng_hist_res.text}"
    eng_records = eng_hist_res.json()["results"]
    print(f"✓ Engineer Alex Vance sees {len(eng_records)} submitted records.")
    for rec in eng_records:
        assert rec["engineer_name"] == "Alex Vance", "Engineer saw records belonging to another user!"

    # -------------------------------------------------------------
    # Step 9: Login as Supervisor
    # -------------------------------------------------------------
    print_step(9, "Login as Supervisor (marcus.brody@gmail.com)")
    super_res = session.post(f"{BASE_URL}/auth/login/", json={
        "email": "marcus.brody@gmail.com",
        "password": "Supervisor@123"
    })
    assert super_res.status_code == 200, f"Supervisor login failed: {super_res.text}"
    super_tokens = super_res.json()
    super_token = super_tokens["access"]
    print(f"✓ Supervisor authenticated: {super_tokens['user']['email']} (Role: {super_tokens['user']['role']})")

    # -------------------------------------------------------------
    # Step 10: Supervisor Reviews Inspections
    # -------------------------------------------------------------
    print_step(10, "Supervisor Reviews Inspections (Confirm & Correct)")
    # 1. Confirm single inspection #single_id
    conf_res = session.post(f"{BASE_URL}/inspections/{single_id}/review/", json={
        "action": "confirm",
        "comment": "Confirmed by Quality Supervisor Marcus Brody."
    }, headers={"Authorization": f"Bearer {super_token}"})
    assert conf_res.status_code == 200, f"Confirm failed: {conf_res.text}"
    conf_data = conf_res.json()
    print(f"✓ Inspection #{single_id} Confirmed:")
    print(f"    - Original AI Class: {conf_data['predicted_class']}")
    print(f"    - Supervisor Class : {conf_data['supervisor_class']}")
    print(f"    - Review Status    : {conf_data['review_status']}")
    print(f"    - Reviewer Name    : {conf_data['supervisor_name']}")
    assert conf_data["review_status"] == "confirmed"
    assert conf_data["predicted_class"] == "Defective"
    assert conf_data["supervisor_class"] == "Defective"

    # 2. Correct batch item 3 (inspection_003.png)
    item3_id = valid_item3["id"]
    corr_res = session.post(f"{BASE_URL}/inspections/{item3_id}/review/", json={
        "action": "correct",
        "corrected_class": "Normal",
        "comment": "Superficial manufacturing oil streak, micrometer depth gauge passed."
    }, headers={"Authorization": f"Bearer {super_token}"})
    assert corr_res.status_code == 200, f"Correct failed: {corr_res.text}"
    corr_data = corr_res.json()
    print(f"✓ Inspection #{item3_id} Corrected:")
    print(f"    - Original AI Class: {corr_data['predicted_class']} (Immutable)")
    print(f"    - Supervisor Class : {corr_data['supervisor_class']} (Overridden)")
    print(f"    - Review Status    : {corr_data['review_status']}")
    assert corr_data["predicted_class"] == "Defective"  # Original output preserved!
    assert corr_data["supervisor_class"] == "Normal"
    assert corr_data["review_status"] == "corrected"

    # -------------------------------------------------------------
    # Step 11: Verify Persistence Survives Re-Retrieval
    # -------------------------------------------------------------
    print_step(11, "Verify Persistence & Immutability Across Reload")
    reload_res = session.get(f"{BASE_URL}/inspections/{item3_id}/", headers={
        "Authorization": f"Bearer {super_token}"
    })
    assert reload_res.status_code == 200, f"Reload failed: {reload_res.text}"
    reloaded = reload_res.json()
    assert reloaded["predicted_class"] == "Defective"
    assert reloaded["confidence"] == 1.0
    assert reloaded["supervisor_class"] == "Normal"
    assert reloaded["review_status"] == "corrected"
    assert reloaded["supervisor_name"] == "Marcus Brody"
    print("✓ Immutability and persistence verified across database reloads.")

    # -------------------------------------------------------------
    # Step 12: Verify RBAC Denial for Engineer Review Attempt
    # -------------------------------------------------------------
    print_step(12, "Verify RBAC Enforcement (Engineer Receives HTTP 403 on Review)")
    unauthorized_res = session.post(f"{BASE_URL}/inspections/{single_id}/review/", json={
        "action": "confirm"
    }, headers={"Authorization": f"Bearer {eng_token}"})
    assert unauthorized_res.status_code == 403, f"Expected 403, got: {unauthorized_res.status_code}"
    print(f"✓ Engineer review call strictly denied with HTTP 403: {unauthorized_res.json()}")

    print("\n" + "=" * 70)
    print(" ALL 34 END-TO-END ACCEPTANCE CRITERIA PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_acceptance()

