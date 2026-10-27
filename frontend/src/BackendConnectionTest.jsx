
import { useState } from "react";
import { createGoal, updateGoal, getGoal } from "./api/goals";

const TEST_USER_ID = "00000000-0000-0000-0000-000000000001";

const TEST_GOALS = {
  effective_date: new Date().toLocaleDateString("en-CA"),
  calories: 2000,
  protein: 100,
  carbs: 250,
  cholesterol: 300,
  trans_fats: 0,
  saturated_fats: 20,
  total_fats: 65,
};

export default function BackendConnectionTest() {
  const [results, setResults] = useState({});
  const [loading, setLoading] = useState(false);

  async function testEndpoint(name, request) {
    setLoading(true);

    try {
      const result = await request();

      setResults((previous) => ({
        ...previous,
        [name]: {
          status: result.status,
          response: result.data,
        },
      }));
    } catch (error) {
      setResults((previous) => ({
        ...previous,
        [name]: {
          status: error.status ?? "Connection failed",
          response: error.data ?? error.message,
        },
      }));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section
      style={{
        maxWidth: "650px",
        margin: "30px auto",
        padding: "20px",
        border: "1px solid #ccc",
        borderRadius: "12px",
      }}
    >
      <h2>Nutrition Goals API Connection Test</h2>

      <p>
        Test the actual FastAPI nutrition goals endpoints.
      </p>

      <p>
        <strong>Test User ID:</strong> {TEST_USER_ID}
      </p>

      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "10px",
          marginBottom: "20px",
        }}
      >
        <button
          type="button"
          disabled={loading}
          onClick={() =>
            testEndpoint("GET", () => getGoal(TEST_USER_ID))
          }
        >
          Test GET
        </button>

        <button
          type="button"
          disabled={loading}
          onClick={() =>
            testEndpoint("PUT", () =>
              updateGoal(TEST_USER_ID, TEST_GOALS)
            )
          }
        >
          Test PUT
        </button>

        <button
          type="button"
          disabled={loading}
          onClick={() =>
            testEndpoint("POST", () =>
              createGoal(TEST_USER_ID, TEST_GOALS)
            )
          }
        >
          Test POST
        </button>
      </div>

      {["GET", "PUT", "POST"].map((method) => (
        <div key={method} style={{ marginBottom: "18px" }}>
          <h3>{method} Response</h3>

          <p>
            <strong>HTTP Status:</strong>{" "}
            {results[method]?.status ?? "Not tested"}
          </p>

          <pre
            style={{
              background: "#f4f4f4",
              padding: "12px",
              borderRadius: "8px",
              whiteSpace: "pre-wrap",
              overflowWrap: "anywhere",
            }}
          >
            {results[method]
              ? JSON.stringify(results[method].response, null, 2)
              : "Click the corresponding button to test."}
          </pre>
        </div>
      ))}
    </section>
  );
}
