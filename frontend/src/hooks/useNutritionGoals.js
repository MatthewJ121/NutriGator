import { useEffect, useState } from "react";
import { getGoal } from "../api/goals";
// MIN/MAX: import { getGoalTypes } from "../api/goalTypes";
import { getLocalDate, pickCurrentGoals } from "../utils/nutrition";

export const DEMO_GOALS = {
  calories: { target: 2100 },
  protein: { target: 95 },
  carbs: { target: 275 },
  cholesterol: { target: 300 },
  saturated_fats: { target: 20 },
  total_fats: { target: 90 },
};

export default function useNutritionGoals(userId, isDemo = false, onUnauthorized, selectedDate = getLocalDate()) {
  const [goals, setGoals] = useState(isDemo ? DEMO_GOALS : {});
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(!isDemo && Boolean(userId));

  useEffect(() => {
    if (isDemo || !userId) {
      return;
    }

    let active = true;
    getGoal(userId)
      .then((goalResult) => {
        if (!active) return;
        const { goals: savedGoals } = pickCurrentGoals(goalResult.data.goals, selectedDate);
        setLoadError("");
        setGoals(savedGoals);
      })
    // MIN/MAX: load the min/max too
    // Promise.all([getGoal(userId), getGoalTypes(userId)])
    //   .then(([goalResult, typeRows]) => {
    //     const { goals: savedGoals } = pickCurrentGoals(goalResult.data.goals, typeRows);
    //     setGoals(savedGoals);
    //   })
      .catch((err) => {
        if (!active) return;
        if (err.status === 401) onUnauthorized?.();
        else setLoadError(err.message);
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [userId, isDemo, onUnauthorized, selectedDate]);

  return { goals, setGoals, loadError, loading };
}
