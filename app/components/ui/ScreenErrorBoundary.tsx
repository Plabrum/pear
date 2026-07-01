import { Component, type ReactNode } from 'react';
import { View, Text, Pressable } from '@/lib/tw';
import Splash from '@/components/ui/Splash';
import { isApiError } from '@/lib/api/errors';

interface Props {
  children: ReactNode;
  onRetry?: () => void;
}

interface State {
  error: Error | null;
}

export default class ScreenErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  handleRetry = () => {
    this.props.onRetry?.();
    this.setState({ error: null });
  };

  render() {
    const { error } = this.state;
    if (!error) return this.props.children;

    // A 401 means the session just died; the HTTP layer has invalidated the
    // session query and the gate is about to redirect to login. Show the neutral
    // loading skeleton during that handoff rather than a scary error screen.
    if (isApiError(error) && error.isUnauthorized) return <Splash variant="spinner" />;

    // An unreachable backend is recoverable — offer a clearly "offline" state and
    // a retry, not a generic "something broke" screen.
    const offline = isApiError(error) && error.isNetworkError;
    const title = offline ? "Can't reach the server" : 'Something went wrong.';
    const body = offline ? 'Check your connection and try again.' : undefined;

    return (
      <View className="flex-1 items-center justify-center gap-3 px-6 bg-background">
        <Text className="text-foreground text-18 font-sans text-center">{title}</Text>
        {body && (
          <Text className="text-foreground-muted text-15 font-sans text-center">{body}</Text>
        )}
        <Pressable
          onPress={this.handleRetry}
          className="mt-2 px-6 py-3 bg-primary rounded-13 active:opacity-80"
        >
          <Text className="text-white text-15 font-sans font-semibold">Try again</Text>
        </Pressable>
      </View>
    );
  }
}
