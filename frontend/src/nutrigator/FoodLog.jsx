
import { useEffect, useState } from "react";
import "./FoodLog.css";
import { getTodaysMeals, logMeal } from "../api/meals";
import {
  NUTRIENT_FIELDS,
  makeEmptyMealDraft,
  parseMealDraft,
} from "../utils/nutrition";

function formatTime(consumedAt) {
  const when = new Date(consumedAt);

  if (Number.isNaN(when.getTime())) {
    return "";
  }

  return when.toLocaleTimeString([], {
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function FoodLog({
  userId,
  isDemo = false,
  onMealsChange,
}) {
  const [meals, setMeals] = useState([]);
  const [loadError, setLoadError] = useState("");
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(makeEmptyMealDraft());
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  useEffect(() => {
    if (isDemo || !userId) {
      return;
    }

    getTodaysMeals()
      .then((savedMeals) => {
        setMeals(savedMeals);
        onMealsChange?.(savedMeals);
      })
      .catch((err) => setLoadError(err.message));
  }, [userId, isDemo, onMealsChange]);

  const addMeal = (meal) => {
    const newMeals = [...meals, meal].sort((a, b) =>
      String(a.consumed_at).localeCompare(String(b.consumed_at))
    );

    setMeals(newMeals);
    onMealsChange?.(newMeals);
  };

  const openForm = () => {
    setDraft(makeEmptyMealDraft());
    setOpen(true);
    setError("");
    setSuccess("");
  };

  const cancelForm = () => {
    setDraft(makeEmptyMealDraft());
    setOpen(false);
    setError("");
    setSuccess("Cancelled. Nothing was logged.");
  };

  const handleChange = (key, value) => {
    setError("");
    setDraft((previous) => ({
      ...previous,
      [key]: value,
    }));
  };

  const handleSave = async (event) => {
    event.preventDefault();

    setError("");
    setSuccess("");

    const result = parseMealDraft(draft);

    if (result.error) {
      setError(result.error);
      return;
    }

    if (isDemo) {
      addMeal({
        ...result.meal,
        meal_id: `demo-${Date.now()}`,
        consumed_at: new Date().toISOString(),
      });
      setOpen(false);
      setSuccess(
        `${result.meal.food_name} logged (demo only, not saved to the database).`
      );
      return;
    }

    if (!userId) {
      setError("No user ID found. Please log in again.");
      return;
    }

    setSaving(true);

    try {
      const savedMeal = await logMeal(result.meal);

      addMeal(savedMeal);
      setOpen(false);
      setSuccess(`${savedMeal.food_name} logged!`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to log meal."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="foodLog">
      <div className="foodLogHeader">
        <h3>Food Log</h3>

        {!open && (
          <button
            type="button"
            className="flButton"
            onClick={openForm}
          >
            + Log Food
          </button>
        )}
      </div>

      {success && (
        <p
          role="status"
          style={{ color: "#16703c" }}
        >
          {success}
        </p>
      )}

      {loadError && (
        <p
          role="alert"
          style={{ color: "#b42318" }}
        >
          {loadError}
        </p>
      )}

      {open && (
        <form
          className="foodLogForm"
          onSubmit={handleSave}
          noValidate
        >
          <label className="foodLogFoodField">
            Food
            <input
              type="text"
              placeholder="e.g. Chicken and rice"
              maxLength={200}
              disabled={saving}
              value={draft.food_name}
              onChange={(event) =>
                handleChange("food_name", event.target.value)
              }
            />
          </label>

          <p className="foodLogHint">
            The time is saved automatically when you log it.
          </p>

          <div className="foodLogGrid">
            {NUTRIENT_FIELDS.map(({ key, label, unit }) => (
              <label key={key}>
                {label}
                {unit ? ` (${unit})` : ""}

                <input
                  type="number"
                  min="0"
                  step="any"
                  placeholder="0"
                  disabled={saving}
                  value={draft[key]}
                  onChange={(event) =>
                    handleChange(key, event.target.value)
                  }
                />
              </label>
            ))}
          </div>

          {error && (
            <p
              role="alert"
              style={{ color: "#b42318" }}
            >
              {error}
            </p>
          )}

          <div className="flButtons">
            <button
              type="button"
              className="flButton"
              onClick={cancelForm}
              disabled={saving}
            >
              Cancel
            </button>

            <button
              type="submit"
              className="flButton flPrimary"
              disabled={saving}
            >
              {saving ? "Saving..." : "Save Meal"}
            </button>
          </div>
        </form>
      )}

      {meals.length === 0 ? (
        <p className="foodLogEmpty">
          Nothing logged today yet.
        </p>
      ) : (
        <ul className="foodLogList">
          {meals.map((meal) => (
            <li key={meal.meal_id}>
              <div className="foodLogName">
                <span>{meal.food_name}</span>
                <span className="foodLogTime">
                  {formatTime(meal.consumed_at)}
                </span>
              </div>

              <div className="foodLogNumbers">
                {meal.calories} cals · {meal.protein}g protein
                · {meal.carbs}g carbs · {meal.total_fats}g fat
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
