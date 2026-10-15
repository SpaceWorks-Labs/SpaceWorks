import { Component, type ErrorInfo, type ReactNode } from "react";

import { CenteredCardLayout } from "../../components/layouts";

type Props = {
  children: ReactNode;
  resetKey: string;
};

type State = {
  error: Error | null;
};

export class StaffPanelErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Staff panel render failed", error, info);
  }

  componentDidUpdate(previous: Props) {
    if (previous.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (!this.state.error) return this.props.children;

    return <CenteredCardLayout standalone={false} state={{ status: "ready" }}
      media={{ icon: "TriangleAlert", tone: "danger" }} title="This page couldn't load"
      body="Something went wrong on our side. Reloading usually fixes it."
      primary={{ label: "Reload page", onClick: () => window.location.reload() }} />;
  }
}
