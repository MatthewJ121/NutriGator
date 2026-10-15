
import { useState } from "react";
import "./ProgressDashboard.css";

// Default nutrition goals
const initialGoals = {
  calories: 2100,
  protein: 95,
  carbs: 275,
  cholesterol: 300,
  trans_fats: 0,
  saturated_fats: 20,
  total_fats: 90,
  fluids: 3.0,
};

// Temporary totals for frontend display
const sampleTotals = {
  calories: 0,
  protein: 0,
  carbs: 0,
  cholesterol: 0,
  trans_fats: 0,
  saturated_fats: 0,
  total_fats: 0,
  fluids: 0,
};

// Goal fields
const fields = [
  { key: "calories", label: "Calories", unit: "" },
  { key: "protein", label: "Protein", unit: "g" },
  { key: "carbs", label: "Carbs", unit: "g" },
  { key: "cholesterol", label: "Cholesterol", unit: "mg" },
  { key: "trans_fats", label: "Trans Fats", unit: "g" },
  { key: "saturated_fats", label: "Saturated Fats", unit: "g" },
  { key: "total_fats", label: "Total Fats", unit: "g" },
  { key: "fluids", label: "Fluids", unit: "L" },
];

// Circular progress indicator
function Ring({ title, subtitle, percent, size = 120 }) {
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  const clamped = Math.max(0, Math.min(percent, 100));

  return (
    <div className="tdRing">
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        aria-hidden="true"
      >
        <circle
          className="tdRingTrack"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
        />

        <circle
          className="tdRingFill"
          cx={size / 2}
          cy={size / 2}
          r={radius}
          strokeWidth={stroke}
          strokeDasharray={`${
            (circumference * clamped) / 100
          } ${circumference}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>

      <div className="tdRingText">
        <div className="tdRingTitle">{title}</div>
        <div className="tdRingSub">{subtitle}</div>
      </div>
    </div>
  );
}

export default function ProgressDashboard() {
  const [slide, setSlide] = useState(0);

  const [goals, setGoals] = useState({
    ...initialGoals,
  });

  const [draftGoals, setDraftGoals] = useState({
    ...initialGoals,
  });

  const [editing, setEditing] = useState(false);

  // Remaining calories
  const remainingCalories = Math.max(
    0,
    goals.calories - sampleTotals.calories
  );

  // Remaining fluids
  const remainingFluids = Math.max(
    0,
    goals.fluids - sampleTotals.fluids
  );

  // Calorie ring percentage
  const caloriePercent =
    goals.calories > 0
      ? (remainingCalories / goals.calories) * 100
      : 0;

  // Open Edit Goals form
  const startEditing = () => {
    setDraftGoals({ ...goals });
    setEditing(true);
  };

  // Cancel without saving
  const cancelEditing = () => {
    setDraftGoals({ ...goals });
    setEditing(false);
  };

  // Update a field while typing
  const handleGoalChange = (key, value) => {
    setDraftGoals((previous) => ({
      ...previous,
      [key]: value,
    }));
  };

  // Save edited goals in frontend state
  const saveGoals = (event) => {
    event.preventDefault();

    const updatedGoals = {};

    fields.forEach(({ key }) => {
      updatedGoals[key] = Number(draftGoals[key]);
    });

    setGoals(updatedGoals);
    setEditing(false);
  };

  return (
    <section
      className="tdOuter"
      aria-label="Nutrition progress"
    >
      <div className="tdWidget">
        {slide === 0 ? (
          <div className="tdCardsRow">

            {/* CALORIES CARD */}
            <div className="tdMiniCard tdCaloriesCard">
              <Ring
                title={remainingCalories}
                subtitle="Cals Remaining"
                percent={caloriePercent}
              />
            </div>

            {/* NUTRITION GOALS CARD */}
            <div className="tdMiniCard tdGoalCard">
              <div className="tdGoalTitle">
                Goal
              </div>

              {fields
                .filter(({ key }) => key !== "fluids")
                .map(({ key, label, unit }) => (
                  <div
                    className="tdGoalLine"
                    key={key}
                  >
                    {label === "Calories"
                      ? "Cals"
                      : label}
                    :{" "}
                    {sampleTotals[key]}/
                    {goals[key]}
                    {unit}
                  </div>
                ))}
            </div>

            {/* HYDRATION CARD */}
            <div className="tdMiniCard tdHydCard">
              <div className="tdHydTitle">
                Hydration
              </div>

              <div className="tdHydLine">
                Fluids:{" "}
                {sampleTotals.fluids.toFixed(1)}/
                {goals.fluids.toFixed(1)}L
              </div>

              <div className="tdHydCheer">
                {remainingFluids > 0
                  ? `Only ${remainingFluids.toFixed(
                      1
                    )}L more to go, you got this!`
                  : "You've reached your hydration goal!"}
              </div>
            </div>
          </div>
        ) : (
          <div className="tdSecondGrid">

            {/* MOTIVATION CARD */}
            <div className="tdMiniCard tdMessageCard">
              <div className="tdSpeechBubble">
                You are doing great! Keep logging
                to keep up the progress!
              </div>
            </div>

            {/* DAY STREAK CARD */}
            <div className="tdMiniCard tdCenterRing">
              <Ring
                title="0"
                subtitle="Day Streak"
                percent={0}
              />

              <p>
                Log one meal today to increase
                your streak.
              </p>
            </div>

            {/* WEEKLY AVERAGE CARD */}
            <div className="tdMiniCard tdCenterRing">
              <Ring
                title="0"
                subtitle="Weekly Avg Cals"
                percent={0}
              />

              <p>
                Goal: {goals.calories} cals
              </p>
            </div>
          </div>
        )}

        {/* CAROUSEL DOTS */}
        <div className="tdDots">
          <button
            type="button"
            className={`tdDot ${
              slide === 0 ? "active" : ""
            }`}
            onClick={() => setSlide(0)}
            aria-label="Daily nutrition progress"
            aria-pressed={slide === 0}
          />

          <button
            type="button"
            className={`tdDot ${
              slide === 1 ? "active" : ""
            }`}
            onClick={() => setSlide(1)}
            aria-label="Additional progress"
            aria-pressed={slide === 1}
          />
        </div>
      </div>

      {/* EDIT GOALS BUTTON */}
      <div className="tdGoalActions">
        <button
          type="button"
          className="tdEditButton"
          onClick={
            editing ? cancelEditing : startEditing
          }
        >
          {editing ? "Cancel" : "Edit Goals"}
        </button>
      </div>

      {/* EDIT GOALS FORM */}
      {editing && (
        <form
          className="tdEditForm"
          onSubmit={saveGoals}
        >
          <h3>Manage Nutrition Goals</h3>

          <div className="tdEditGrid">
            {fields.map(({ key, label, unit }) => (
              <label key={key}>
                {label}
                {unit ? ` (${unit})` : ""}

                <input
                  type="number"
                  min="0"
                  step="any"
                  required
                  value={draftGoals[key]}
                  onChange={(event) =>
                    handleGoalChange(
                      key,
                      event.target.value
                    )
                  }
                />
              </label>
            ))}
          </div>

          <button
            type="submit"
            className="tdEditButton"
          >
            Save Goals
          </button>
        </form>
      )}
    </section>
  );
}
