def test_create_and_list_beneficiary(client, auth_headers):
    headers = auth_headers(email="benecreate@example.com")

    response = client.post(
        "/beneficiaries",
        json={
            "full_name": "Jamie Heir",
            "relationship_label": "Sibling",
            "allocation_percentage": "50.00",
            "contact_email": "jamie@example.com",
        },
        headers=headers,
    )
    assert response.status_code == 201

    listed = client.get("/beneficiaries", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["full_name"] == "Jamie Heir"


def test_delete_beneficiary(client, auth_headers):
    headers = auth_headers(email="benedelete@example.com")
    created = client.post(
        "/beneficiaries",
        json={"full_name": "Temp Person", "relationship_label": "Friend"},
        headers=headers,
    ).json()

    response = client.delete(f"/beneficiaries/{created['id']}", headers=headers)
    assert response.status_code == 204
    assert client.get("/beneficiaries", headers=headers).json() == []


def test_beneficiaries_are_scoped_per_user(client, auth_headers):
    headers_a = auth_headers(email="benescopea@example.com")
    headers_b = auth_headers(email="benescopeb@example.com")
    client.post(
        "/beneficiaries",
        json={"full_name": "A's Person", "relationship_label": "Spouse"},
        headers=headers_a,
    )

    assert client.get("/beneficiaries", headers=headers_b).json() == []
    assert len(client.get("/beneficiaries", headers=headers_a).json()) == 1


def test_delete_beneficiary_rejects_non_owner(client, auth_headers):
    headers_a = auth_headers(email="benedelownera@example.com")
    headers_b = auth_headers(email="benedelownerb@example.com")
    created = client.post(
        "/beneficiaries",
        json={"full_name": "Owned by A", "relationship_label": "Child"},
        headers=headers_a,
    ).json()

    response = client.delete(f"/beneficiaries/{created['id']}", headers=headers_b)
    assert response.status_code == 404
