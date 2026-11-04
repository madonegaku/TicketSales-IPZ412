import { Meteor } from "meteor/meteor";
import { useTracker } from "meteor/react-meteor-data";
import { useCallback, useEffect, useState } from "react";

// Поточний користувач і його ролі (публікації «me» і призначень ролей із server/accounts.js).
export function useCurrentUser() {
  return useTracker(() => {
    const handle = Meteor.subscribe("me");
    const user = Meteor.user();
    const roles = user
      ? Meteor.roleAssignment.find({ "user._id": user._id }).map((assignment) => assignment.role._id)
      : [];
    return { user, roles, loading: Meteor.loggingIn() || !handle.ready() };
  }, []);
}

export function hasRole(roles, ...wanted) {
  return wanted.some((role) => roles.includes(role));
}

// Виклик методу Meteor із станом завантаження й помилки; reload() – повторити.
export function useMethod(name, ...args) {
  const [state, setState] = useState({ data: undefined, error: null, loading: true });
  const key = JSON.stringify(args);
  const reload = useCallback(() => {
    setState((previous) => ({ ...previous, loading: true }));
    Meteor.callAsync(name, ...args)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => setState({ data: undefined, error: messageOf(error), loading: false }));
  }, [name, key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(reload, [reload]);
  return { ...state, reload };
}

export function messageOf(error) {
  return error?.reason || error?.message || "Невідома помилка.";
}
