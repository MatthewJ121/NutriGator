import { useState } from "react";
import "../ProgressDashboard.css";
import GoalsEditor from "./GoalsEditor";
import useNutritionGoals from "../hooks/useNutritionGoals";
import { NUTRIENT_FIELDS, makeZeroTotals } from "../utils/nutrition";

const fluidsGoal = 3.0;
const fluidsDrank = 0;

function roundNumber(value) {
  return Math.round(value * 10) / 10;
}

function Ring({
  title,
  subtitle,
  percent,
  size = 120,
}) {
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;

  const clamped = Math.max(
    0,
    Math.min(percent, 100)
  );

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

export default function GoalsDashboard({
  userId,
  isDemo = false,
  totals = makeZeroTotals(),
}) {
  const [slide, setSlide] = useState(0);
  const { goals, setGoals, loadError } = useNutritionGoals(userId, isDemo);

  const [editing, setEditing] = useState(false);
  const [success, setSuccess] = useState("");

  const calorieGoal = goals.calories;

  const remainingCalories = calorieGoal
    ? Math.max(0, roundNumber(calorieGoal.target - totals.calories))
    : 0;

  const remainingFluids = Math.max(
    0,
    fluidsGoal - fluidsDrank
  );

  const caloriePercent = calorieGoal
    ? (remainingCalories / calorieGoal.target) * 100
    : 0;

  const startEditing = () => {
    setEditing(true);
    setSuccess("");
  };

  const handleGoalsSaved = (newGoals, message) => {
    setGoals(newGoals);
    setEditing(false);
    setSuccess(message);
  };

  const handleGoalsCancelled = (message) => {
    setEditing(false);
    setSuccess(message);
  };

  const trackedFields = NUTRIENT_FIELDS.filter(
    ({ key }) => goals[key]
  );

  return (
    <section
      className="tdOuter"
      aria-label="Nutrition progress"
    >
      <div className="tdWidget">
        {slide === 0 ? (
          <div className="tdCardsRow">
            {/* CALORIES */}
            <div className="tdMiniCard tdCaloriesCard">
              {calorieGoal ? (
                <Ring
                  title={remainingCalories}
                  subtitle="Cals Remaining"
                  percent={caloriePercent}
                />
              ) : (
                <Ring
                  title={roundNumber(totals.calories)}
                  subtitle="Cals Eaten"
                  percent={0}
                />
              )}
            </div>

            {/* NUTRITION GOALS */}
            <div className="tdMiniCard tdGoalCard">
              <div className="tdGoalTitle">
                Goal
              </div>

              {trackedFields.length === 0 && (
                <div className="tdGoalLine">
                  No goals selected yet.
                </div>
              )}

              {trackedFields.map(
                ({ key, label, unit }) => (
                  <div
                    className="tdGoalLine"
                    key={key}
                  >
                    {label === "Calories"
                      ? "Cals"
                      : label}
                    : {roundNumber(totals[key])}/
                    {goals[key].target}
                    {unit}
                    {/* MIN/MAX: {" "}({goals[key].type}) */}
                  </div>
                )
              )}
            </div>

            {/* HYDRATION */}
            <div className="tdMiniCard tdHydCard">
              <div className="tdHydTitle">
                Hydration
              </div>

              <div className="tdHydLine">
                Fluids:{" "}
                {fluidsDrank.toFixed(1)}/
                {fluidsGoal.toFixed(1)}L
              </div>

              <div className="tdHydCheer">
                {remainingFluids > 0
                  ? `Only ${remainingFluids.toFixed(1)}L more to go, you got this!`
                  : "You've reached your hydration goal!"}
              </div>
            </div>
          </div>
        ) : (
          <div className="tdSecondGrid">
            {/* MOTIVATION */}
            <div className="tdMiniCard tdMessageCard">
              <div className="tdSpeechBubble">
                You are doing great! Keep logging
                to keep up the progress!
              </div>
            </div>

            {/* DAY STREAK */}
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

            {/* WEEKLY AVERAGE */}
            <div className="tdMiniCard tdCenterRing">
              <Ring
                title="0"
                subtitle="Weekly Avg Cals"
                percent={0}
              />

              <p>
                Goal:{" "}
                {calorieGoal
                  ? `${calorieGoal.target} cals`
                  : "not set"}
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

      {/* SUCCESS MESSAGE */}
      {success && (
        <p
          role="status"
          style={{ color: "#16703c" }}
        >
          {success}
        </p>
      )}

      {/* ERROR MESSAGE */}
      {loadError && (
        <p
          role="alert"
          style={{ color: "#b42318" }}
        >
          {loadError}
        </p>
      )}

      {/* EDIT BUTTON */}
      {!editing && (
        <div className="tdGoalActions">
          <button
            type="button"
            className="tdEditButton"
            onClick={startEditing}
          >
            Edit Goals
          </button>
        </div>
      )}

      {/* EDIT FORM */}
      {editing && (
        <GoalsEditor
          userId={userId}
          isDemo={isDemo}
          goals={goals}
          onSaved={handleGoalsSaved}
          onCancel={handleGoalsCancelled}
        />
      )}
    </section>
  );
}
