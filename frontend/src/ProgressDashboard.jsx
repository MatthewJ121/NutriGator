
import { useState } from "react";
import "./ProgressDashboard.css";

const initialGoals = {
  calories: 2100,
  carbs: 275,
  protein: 95,
  fats: 90,
  fiber: 25,
  sugar: 50,
  sodium: 2300,
  fluids: 3.0,
};

const sampleTotals = {
  calories: 0,
  carbs: 0,
  protein: 0,
  fats: 0,
  fiber: 0,
  sugar: 0,
  sodium: 0,
  fluids: 0,
};

const fields = [
  { key: "calories", label: "Calories", unit: "" },
  { key: "carbs", label: "Carbs", unit: "g" },
  { key: "protein", label: "Protein", unit: "g" },
  { key: "fats", label: "Fats", unit: "g" },
  { key: "fiber", label: "Fiber", unit: "g" },
  { key: "sugar", label: "Sugar", unit: "g" },
  { key: "sodium", label: "Sodium", unit: "mg" },
  { key: "fluids", label: "Fluids", unit: "L" },
];

function Ring({ title, subtitle, percent, size = 100 }) {
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
          strokeDasharray={`${circumference * clamped / 100} ${circumference}`}
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
  const [goals, setGoals] = useState(initialGoals);
  const [draftGoals, setDraftGoals] = useState(initialGoals);
  const [editing, setEditing] = useState(false);

  const remainingCalories = Math.max(
    0,
    goals.calories - sampleTotals.calories
  );

  const remainingFluids = Math.max(
    0,
    goals.fluids - sampleTotals.fluids
  );

  const startEditing = () => {
    setDraftGoals({ ...goals });
    setEditing(true);
  };

  const saveGoals = (e) => {
    e.preventDefault();

    const updated = {};
    fields.forEach(({ key }) => {
      updated[key] = Number(draftGoals[key]);
    });

    setGoals(updated);
    setEditing(false);
  };

  return (
    <section className="tdOuter" aria-label="Nutrition progress">
      <div className="tdWidget">
        {slide === 0 ? (
          <div className="tdCardsRow">
            <div className="tdMiniCard tdCaloriesCard">
              <Ring
                title={remainingCalories}
                subtitle="Cals Remaining"
                percent={
                  goals.calories > 0
                    ? remainingCalories / goals.calories * 100
                    : 0
                }
              />
            </div>

            <div className="tdMiniCard tdGoalCard">
              <div className="tdGoalTitle">Goal</div>

              {fields
                .filter(({ key }) => key !== "fluids")
                .map(({ key, label, unit }) => (
                  <div className="tdGoalLine" key={key}>
                    {label === "Calories" ? "Cals" : label}:{" "}
                    {sampleTotals[key]}/{goals[key]}{unit}
                  </div>
                ))}
            </div>

            <div className="tdMiniCard tdHydCard">
              <div className="tdHydTitle">Hydration</div>

              <div className="tdHydLine">
                Fluids: {sampleTotals.fluids.toFixed(1)}/
                {goals.fluids.toFixed(1)}L
              </div>

              <div className="tdHydCheer">
                Only {remainingFluids.toFixed(1)}L more to go,
                you got this!
              </div>
            </div>
          </div>
        ) : (
          <div className="tdSecondGrid">
            <div className="tdMiniCard tdMessageCard">
              <div className="tdSpeechBubble">
                You are doing great! Keep logging to keep up
                the progress!
              </div>
            </div>

            <div className="tdMiniCard tdCenterRing">
              <Ring
                title="0"
                subtitle="Day Streak"
                percent={0}
              />
              <p>Log one meal today to increase your streak.</p>
            </div>

            <div className="tdMiniCard tdCenterRing">
              <Ring
                title="0"
                subtitle="Weekly Avg Cals"
                percent={0}
              />
              <p>Goal: {goals.calories} cals</p>
            </div>
          </div>
        )}

        <div className="tdDots">
          <button
            type="button"
            className={`tdDot ${slide === 0 ? "active" : ""}`}
            onClick={() => setSlide(0)}
            aria-label="Daily nutrition progress"
            aria-pressed={slide === 0}
          />

          <button
            type="button"
            className={`tdDot ${slide === 1 ? "active" : ""}`}
            onClick={() => setSlide(1)}
            aria-label="Additional progress"
            aria-pressed={slide === 1}
          />
        </div>
      </div>

      <div className="tdGoalActions">
        <button
          type="button"
          className="tdEditButton"
          onClick={() => {
            if (editing) {
              setEditing(false);
            } else {
              startEditing();
            }
          }}
        >
          {editing ? "Cancel" : "Edit Goals"}
        </button>
      </div>

      {editing && (
        <form className="tdEditForm" onSubmit={saveGoals}>
          <h3>Manage Nutrition Goals</h3>

          <div className="tdEditGrid">
            {fields.map(({ key, label, unit }) => (
              <label key={key}>
                {label} {unit && `(${unit})`}
                <input
                  type="number"
                  min="0.1"
                  step="any"
                  required
                  value={draftGoals[key]}
                  onChange={(e) =>
                    setDraftGoals((prev) => ({
                      ...prev,
                      [key]: e.target.value,
                    }))
                  }
                />
              </label>
            ))}
          </div>

          <button type="submit" className="tdEditButton">
            Save Goals
          </button>
        </form>
      )}
    </section>
  );
}
