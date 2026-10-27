import { useState } from "react";
import "./GoalsEditor.css";
import { createGoal, updateGoal } from "../api/goals";
// MIN/MAX: import { saveGoalTypes } from "../api/goalTypes";
import {
  NUTRIENT_FIELDS,
  getLocalDate,
  makeDraftGoals,
  makeGoalRequests,
  parseGoalDraft,
} from "../utils/nutrition";

async function saveGoals(userId, goals) {
  const { values } = makeGoalRequests(goals, getLocalDate());

  try {
    await createGoal(userId, values);
  } catch (err) {
    if (err.status !== 409) {
      throw err;
    }
    await updateGoal(userId, values);
  }

  // MIN/MAX: await saveGoalTypes(userId, types);
}

export default function GoalsEditor({
  userId,
  isDemo = false,
  goals,
  onSaved,
  onCancel,
}) {
  const [draftGoals, setDraftGoals] = useState(
    makeDraftGoals(goals)
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const handleDraftChange = (key, part, value) => {
    setError("");
    setDraftGoals((previous) => ({
      ...previous,
      [key]: {
        ...previous[key],
        [part]: value,
      },
    }));
  };

  const handleCancel = () => {
    setDraftGoals(makeDraftGoals(goals));
    onCancel("Changes cancelled. Your goals were not changed.");
  };

  const handleSave = async (event) => {
    event.preventDefault();
    setError("");

    const result = parseGoalDraft(draftGoals);

    if (result.error) {
      setError(result.error);
      return;
    }

    if (isDemo) {
      onSaved(
        result.goals,
        "Demo goals updated. These changes are not saved to the database."
      );
      return;
    }

    if (!userId) {
      setError("No user ID found. Please log in again.");
      return;
    }

    setSaving(true);

    try {
      await saveGoals(userId, result.goals);

      onSaved(result.goals, "Nutrition goals saved!");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to save goals."
      );
      setSaving(false);
    }
  };

  return (
    <form
      className="tdEditForm"
      onSubmit={handleSave}
      noValidate
    >
      <h3>Manage Nutrition Goals</h3>
      <p className="geHint">
        Check the goals you want to track and enter a target for each one.
      </p>

      <div className="geRows">
        {NUTRIENT_FIELDS.map(({ key, label, unit }) => {
          const choice = draftGoals[key];

          return (
            <div
              className={`geRow ${choice.tracked ? "" : "geRowOff"}`}
              key={key}
            >
              <label className="geCheck">
                <input
                  type="checkbox"
                  checked={choice.tracked}
                  disabled={saving}
                  onChange={(event) =>
                    handleDraftChange(key, "tracked", event.target.checked)
                  }
                />
                {label}
                {unit ? ` (${unit})` : ""}
              </label>

              {/* MIN/MAX (turned off for now):
              <select
                aria-label={`${label} goal type`}
                value={choice.type}
                disabled={saving || !choice.tracked}
                onChange={(event) =>
                  handleDraftChange(key, "type", event.target.value)
                }
              >
                <option value="max">Max</option>
                <option value="min">Min</option>
              </select>
              */}

              <input
                type="number"
                aria-label={`${label} target`}
                min="0"
                step="any"
                placeholder="Target"
                disabled={saving || !choice.tracked}
                value={choice.target}
                onChange={(event) =>
                  handleDraftChange(key, "target", event.target.value)
                }
              />
            </div>
          );
        })}
      </div>

      {error && (
        <p
          role="alert"
          style={{ color: "#b42318" }}
        >
          {error}
        </p>
      )}

      <div className="geButtons">
        <button
          type="button"
          className="tdEditButton"
          onClick={handleCancel}
          disabled={saving}
        >
          Cancel
        </button>

        <button
          type="submit"
          className="tdEditButton gePrimary"
          disabled={saving}
        >
          {saving ? "Saving..." : "Save Goals"}
        </button>
      </div>
    </form>
  );
}
