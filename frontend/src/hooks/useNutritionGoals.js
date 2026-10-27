import { useEffect, useState } from "react";
import { getGoal } from "../api/goals";
// MIN/MAX: import { getGoalTypes } from "../api/goalTypes";
import { pickCurrentGoals } from "../utils/nutrition";

export const DEMO_GOALS = {
  calories: { target: 2100 },
  protein: { target: 95 },
  carbs: { target: 275 },
  cholesterol: { target: 300 },
  saturated_fats: { target: 20 },
  total_fats: { target: 90 },
};

export default function useNutritionGoals(userId, isDemo = false) {
  const [goals, setGoals] = useState(isDemo ? DEMO_GOALS : {});
  const [loadError, setLoadError] = useState("");

  useEffect(() => {
    if (isDemo || !userId) {
      return;
    }

    getGoal(userId)
      .then((goalResult) => {
        const { goals: savedGoals } = pickCurrentGoals(goalResult.data.goals);
        setGoals(savedGoals);
      })
    // MIN/MAX: load the min/max too
    // Promise.all([getGoal(userId), getGoalTypes(userId)])
    //   .then(([goalResult, typeRows]) => {
    //     const { goals: savedGoals } = pickCurrentGoals(goalResult.data.goals, typeRows);
    //     setGoals(savedGoals);
    //   })
      .catch((err) => setLoadError(err.message));
  }, [userId, isDemo]);

  return { goals, setGoals, loadError };
}
