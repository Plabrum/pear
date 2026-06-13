export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type Database = {
  graphql_public: {
    Tables: {
      [_ in never]: never;
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      graphql: {
        Args: {
          extensions?: Json;
          operationName?: string;
          query?: string;
          variables?: Json;
        };
        Returns: Json;
      };
    };
    Enums: {
      [_ in never]: never;
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
  public: {
    Tables: {
      contacts: {
        Row: {
          created_at: string;
          id: string;
          phone_number: string;
          user_id: string;
          winger_id: string | null;
          wingperson_status: Database['public']['Enums']['wingperson_status'];
        };
        Insert: {
          created_at?: string;
          id?: string;
          phone_number: string;
          user_id: string;
          winger_id?: string | null;
          wingperson_status?: Database['public']['Enums']['wingperson_status'];
        };
        Update: {
          created_at?: string;
          id?: string;
          phone_number?: string;
          user_id?: string;
          winger_id?: string | null;
          wingperson_status?: Database['public']['Enums']['wingperson_status'];
        };
        Relationships: [
          {
            foreignKeyName: 'contacts_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'contacts_winger_id_fkey';
            columns: ['winger_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      dating_profiles: {
        Row: {
          age_from: number;
          age_to: number | null;
          bio: string | null;
          city: Database['public']['Enums']['city'];
          created_at: string;
          dating_status: Database['public']['Enums']['dating_status'];
          id: string;
          interested_gender: Database['public']['Enums']['gender'][];
          interests: Database['public']['Enums']['interest'][];
          is_active: boolean;
          religion: Database['public']['Enums']['religion'];
          religious_preference: Database['public']['Enums']['religion'] | null;
          updated_at: string;
          user_id: string;
        };
        Insert: {
          age_from: number;
          age_to?: number | null;
          bio?: string | null;
          city: Database['public']['Enums']['city'];
          created_at?: string;
          dating_status?: Database['public']['Enums']['dating_status'];
          id?: string;
          interested_gender?: Database['public']['Enums']['gender'][];
          interests?: Database['public']['Enums']['interest'][];
          is_active?: boolean;
          religion: Database['public']['Enums']['religion'];
          religious_preference?: Database['public']['Enums']['religion'] | null;
          updated_at?: string;
          user_id: string;
        };
        Update: {
          age_from?: number;
          age_to?: number | null;
          bio?: string | null;
          city?: Database['public']['Enums']['city'];
          created_at?: string;
          dating_status?: Database['public']['Enums']['dating_status'];
          id?: string;
          interested_gender?: Database['public']['Enums']['gender'][];
          interests?: Database['public']['Enums']['interest'][];
          is_active?: boolean;
          religion?: Database['public']['Enums']['religion'];
          religious_preference?: Database['public']['Enums']['religion'] | null;
          updated_at?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'dating_profiles_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: true;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      decisions: {
        Row: {
          actor_id: string;
          created_at: string;
          decision: Database['public']['Enums']['decision_type'] | null;
          id: string;
          note: string | null;
          recipient_id: string;
          suggested_by: string | null;
        };
        Insert: {
          actor_id: string;
          created_at?: string;
          decision?: Database['public']['Enums']['decision_type'] | null;
          id?: string;
          note?: string | null;
          recipient_id: string;
          suggested_by?: string | null;
        };
        Update: {
          actor_id?: string;
          created_at?: string;
          decision?: Database['public']['Enums']['decision_type'] | null;
          id?: string;
          note?: string | null;
          recipient_id?: string;
          suggested_by?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: 'decisions_actor_id_fkey';
            columns: ['actor_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'decisions_recipient_id_fkey';
            columns: ['recipient_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'decisions_suggested_by_fkey';
            columns: ['suggested_by'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      matches: {
        Row: {
          created_at: string;
          id: string;
          user_a_id: string;
          user_b_id: string;
        };
        Insert: {
          created_at?: string;
          id?: string;
          user_a_id: string;
          user_b_id: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          user_a_id?: string;
          user_b_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'matches_user_a_id_fkey';
            columns: ['user_a_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'matches_user_b_id_fkey';
            columns: ['user_b_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      messages: {
        Row: {
          body: string;
          created_at: string;
          id: string;
          is_read: boolean;
          match_id: string;
          sender_id: string;
        };
        Insert: {
          body: string;
          created_at?: string;
          id?: string;
          is_read?: boolean;
          match_id: string;
          sender_id: string;
        };
        Update: {
          body?: string;
          created_at?: string;
          id?: string;
          is_read?: boolean;
          match_id?: string;
          sender_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'messages_match_id_fkey';
            columns: ['match_id'];
            isOneToOne: false;
            referencedRelation: 'matches';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'messages_sender_id_fkey';
            columns: ['sender_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      profile_photos: {
        Row: {
          approved_at: string | null;
          created_at: string;
          dating_profile_id: string;
          display_order: number;
          id: string;
          rejected_at: string | null;
          storage_url: string;
          suggester_id: string | null;
        };
        Insert: {
          approved_at?: string | null;
          created_at?: string;
          dating_profile_id: string;
          display_order: number;
          id?: string;
          rejected_at?: string | null;
          storage_url: string;
          suggester_id?: string | null;
        };
        Update: {
          approved_at?: string | null;
          created_at?: string;
          dating_profile_id?: string;
          display_order?: number;
          id?: string;
          rejected_at?: string | null;
          storage_url?: string;
          suggester_id?: string | null;
        };
        Relationships: [
          {
            foreignKeyName: 'profile_photos_dating_profile_id_fkey';
            columns: ['dating_profile_id'];
            isOneToOne: false;
            referencedRelation: 'dating_profiles';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'profile_photos_suggester_id_fkey';
            columns: ['suggester_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      profile_prompts: {
        Row: {
          answer: string;
          created_at: string;
          dating_profile_id: string;
          id: string;
          prompt_template_id: string;
        };
        Insert: {
          answer: string;
          created_at?: string;
          dating_profile_id: string;
          id?: string;
          prompt_template_id: string;
        };
        Update: {
          answer?: string;
          created_at?: string;
          dating_profile_id?: string;
          id?: string;
          prompt_template_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'profile_prompts_dating_profile_id_fkey';
            columns: ['dating_profile_id'];
            isOneToOne: false;
            referencedRelation: 'dating_profiles';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'profile_prompts_prompt_template_id_fkey';
            columns: ['prompt_template_id'];
            isOneToOne: false;
            referencedRelation: 'prompt_templates';
            referencedColumns: ['id'];
          },
        ];
      };
      profile_reports: {
        Row: {
          created_at: string;
          id: string;
          reason: string;
          reported_id: string;
          reporter_id: string;
        };
        Insert: {
          created_at?: string;
          id?: string;
          reason: string;
          reported_id: string;
          reporter_id: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          reason?: string;
          reported_id?: string;
          reporter_id?: string;
        };
        Relationships: [];
      };
      profiles: {
        Row: {
          avatar_url: string | null;
          chosen_name: string | null;
          created_at: string;
          date_of_birth: string | null;
          full_name: string | null;
          gender: Database['public']['Enums']['gender'] | null;
          id: string;
          last_name: string | null;
          phone_number: string | null;
          push_token: string | null;
          role: Database['public']['Enums']['user_role'];
          updated_at: string | null;
          username: string | null;
          website: string | null;
        };
        Insert: {
          avatar_url?: string | null;
          chosen_name?: string | null;
          created_at?: string;
          date_of_birth?: string | null;
          full_name?: string | null;
          gender?: Database['public']['Enums']['gender'] | null;
          id: string;
          last_name?: string | null;
          phone_number?: string | null;
          push_token?: string | null;
          role?: Database['public']['Enums']['user_role'];
          updated_at?: string | null;
          username?: string | null;
          website?: string | null;
        };
        Update: {
          avatar_url?: string | null;
          chosen_name?: string | null;
          created_at?: string;
          date_of_birth?: string | null;
          full_name?: string | null;
          gender?: Database['public']['Enums']['gender'] | null;
          id?: string;
          last_name?: string | null;
          phone_number?: string | null;
          push_token?: string | null;
          role?: Database['public']['Enums']['user_role'];
          updated_at?: string | null;
          username?: string | null;
          website?: string | null;
        };
        Relationships: [];
      };
      prompt_responses: {
        Row: {
          created_at: string;
          id: string;
          is_approved: boolean;
          is_rejected: boolean;
          message: string;
          profile_prompt_id: string;
          user_id: string;
        };
        Insert: {
          created_at?: string;
          id?: string;
          is_approved?: boolean;
          is_rejected?: boolean;
          message: string;
          profile_prompt_id: string;
          user_id: string;
        };
        Update: {
          created_at?: string;
          id?: string;
          is_approved?: boolean;
          is_rejected?: boolean;
          message?: string;
          profile_prompt_id?: string;
          user_id?: string;
        };
        Relationships: [
          {
            foreignKeyName: 'prompt_responses_profile_prompt_id_fkey';
            columns: ['profile_prompt_id'];
            isOneToOne: false;
            referencedRelation: 'profile_prompts';
            referencedColumns: ['id'];
          },
          {
            foreignKeyName: 'prompt_responses_user_id_fkey';
            columns: ['user_id'];
            isOneToOne: false;
            referencedRelation: 'profiles';
            referencedColumns: ['id'];
          },
        ];
      };
      prompt_templates: {
        Row: {
          id: string;
          question: string;
        };
        Insert: {
          id?: string;
          question: string;
        };
        Update: {
          id?: string;
          question?: string;
        };
        Relationships: [];
      };
    };
    Views: {
      [_ in never]: never;
    };
    Functions: {
      get_discover_pool:
        | {
            Args: {
              filter_winger_id?: string;
              page_offset?: number;
              page_size?: number;
              viewer_id: string;
            };
            Returns: {
              age: number;
              bio: string;
              chosen_name: string;
              city: Database['public']['Enums']['city'];
              dating_status: Database['public']['Enums']['dating_status'];
              first_photo: string;
              gender: Database['public']['Enums']['gender'];
              interests: Database['public']['Enums']['interest'][];
              profile_id: string;
              suggested_by: string;
              suggester_name: string;
              user_id: string;
              wing_note: string;
            }[];
          }
        | {
            Args: {
              filter_winger_id?: string;
              page_offset?: number;
              page_size?: number;
              viewer_id: string;
              winger_only?: boolean;
            };
            Returns: {
              age: number;
              bio: string;
              chosen_name: string;
              city: Database['public']['Enums']['city'];
              dating_status: Database['public']['Enums']['dating_status'];
              first_photo: string;
              gender: Database['public']['Enums']['gender'];
              interests: Database['public']['Enums']['interest'][];
              profile_id: string;
              suggested_by: string;
              suggester_name: string;
              user_id: string;
              wing_note: string;
            }[];
          };
      get_likes_you_count: { Args: { viewer_id: string }; Returns: number };
      get_likes_you_pool: {
        Args: { page_offset?: number; page_size?: number; viewer_id: string };
        Returns: {
          age: number;
          bio: string;
          chosen_name: string;
          city: Database['public']['Enums']['city'];
          dating_status: Database['public']['Enums']['dating_status'];
          first_photo: string;
          gender: Database['public']['Enums']['gender'];
          interests: Database['public']['Enums']['interest'][];
          profile_id: string;
          suggested_by: string;
          suggester_name: string;
          user_id: string;
          wing_note: string;
        }[];
      };
      get_wing_pool: {
        Args: {
          dater_id: string;
          page_offset?: number;
          page_size?: number;
          winger_id: string;
        };
        Returns: {
          age: number;
          bio: string;
          chosen_name: string;
          city: Database['public']['Enums']['city'];
          dating_status: Database['public']['Enums']['dating_status'];
          first_photo: string;
          gender: Database['public']['Enums']['gender'];
          interests: Database['public']['Enums']['interest'][];
          profile_id: string;
          user_id: string;
        }[];
      };
      is_active_wingperson: { Args: { _dater: string }; Returns: boolean };
    };
    Enums: {
      city: 'Boston' | 'New York';
      dating_status: 'open' | 'break' | 'winging';
      decision_type: 'approved' | 'declined';
      gender: 'Male' | 'Female' | 'Non-Binary';
      interest:
        | 'Travel'
        | 'Fitness'
        | 'Cooking'
        | 'Music'
        | 'Art'
        | 'Movies'
        | 'Books'
        | 'Gaming'
        | 'Outdoors'
        | 'Sports'
        | 'Technology'
        | 'Fashion'
        | 'Food'
        | 'Photography'
        | 'Dance'
        | 'Volunteering';
      religion:
        | 'Muslim'
        | 'Christian'
        | 'Jewish'
        | 'Hindu'
        | 'Buddhist'
        | 'Sikh'
        | 'Agnostic'
        | 'Atheist'
        | 'Other'
        | 'Prefer not to say';
      user_role: 'dater' | 'winger';
      wingperson_status: 'invited' | 'active' | 'removed';
    };
    CompositeTypes: {
      [_ in never]: never;
    };
  };
};

type DatabaseWithoutInternals = Omit<Database, '__InternalSupabase'>;

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, 'public'>];

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema['Tables'] & DefaultSchema['Views'])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables'] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Views'])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables'] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Views'])[TableName] extends {
      Row: infer R;
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema['Tables'] & DefaultSchema['Views'])
    ? (DefaultSchema['Tables'] & DefaultSchema['Views'])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R;
      }
      ? R
      : never
    : never;

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema['Tables']
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables']
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables'][TableName] extends {
      Insert: infer I;
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema['Tables']
    ? DefaultSchema['Tables'][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I;
      }
      ? I
      : never
    : never;

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema['Tables']
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables']
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions['schema']]['Tables'][TableName] extends {
      Update: infer U;
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema['Tables']
    ? DefaultSchema['Tables'][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U;
      }
      ? U
      : never
    : never;

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema['Enums']
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions['schema']]['Enums']
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions['schema']]['Enums'][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema['Enums']
    ? DefaultSchema['Enums'][DefaultSchemaEnumNameOrOptions]
    : never;

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema['CompositeTypes']
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals;
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions['schema']]['CompositeTypes']
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals;
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions['schema']]['CompositeTypes'][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema['CompositeTypes']
    ? DefaultSchema['CompositeTypes'][PublicCompositeTypeNameOrOptions]
    : never;

export const Constants = {
  graphql_public: {
    Enums: {},
  },
  public: {
    Enums: {
      city: ['Boston', 'New York'],
      dating_status: ['open', 'break', 'winging'],
      decision_type: ['approved', 'declined'],
      gender: ['Male', 'Female', 'Non-Binary'],
      interest: [
        'Travel',
        'Fitness',
        'Cooking',
        'Music',
        'Art',
        'Movies',
        'Books',
        'Gaming',
        'Outdoors',
        'Sports',
        'Technology',
        'Fashion',
        'Food',
        'Photography',
        'Dance',
        'Volunteering',
      ],
      religion: [
        'Muslim',
        'Christian',
        'Jewish',
        'Hindu',
        'Buddhist',
        'Sikh',
        'Agnostic',
        'Atheist',
        'Other',
        'Prefer not to say',
      ],
      user_role: ['dater', 'winger'],
      wingperson_status: ['invited', 'active', 'removed'],
    },
  },
} as const;
