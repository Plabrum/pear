import { pgTable, foreignKey, unique, pgPolicy, check, uuid, timestamp, text, date, index, integer, boolean, pgEnum } from "drizzle-orm/pg-core"
import { sql } from "drizzle-orm"

export const city = pgEnum("city", ['Boston', 'New York'])
export const datingStatus = pgEnum("dating_status", ['open', 'break', 'winging'])
export const decisionType = pgEnum("decision_type", ['approved', 'declined'])
export const gender = pgEnum("gender", ['Male', 'Female', 'Non-Binary'])
export const interest = pgEnum("interest", ['Travel', 'Fitness', 'Cooking', 'Music', 'Art', 'Movies', 'Books', 'Gaming', 'Outdoors', 'Sports', 'Technology', 'Fashion', 'Food', 'Photography', 'Dance', 'Volunteering'])
export const religion = pgEnum("religion", ['Muslim', 'Christian', 'Jewish', 'Hindu', 'Buddhist', 'Sikh', 'Agnostic', 'Atheist', 'Other', 'Prefer not to say'])
export const userRole = pgEnum("user_role", ['dater', 'winger'])
export const wingpersonStatus = pgEnum("wingperson_status", ['invited', 'active', 'removed'])


export const profileReports = pgTable("profile_reports", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	reporterId: uuid("reporter_id").notNull(),
	reportedId: uuid("reported_id").notNull(),
	reason: text().notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	pgPolicy("Users can insert their own reports", { as: "permissive", for: "insert", to: ["public"], withCheck: sql`(auth.uid() = reporter_id)` }),
]);

export const profiles = pgTable("profiles", {
	id: uuid().primaryKey().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }),
	username: text(),
	fullName: text("full_name"),
	avatarUrl: text("avatar_url"),
	website: text(),
	chosenName: text("chosen_name"),
	lastName: text("last_name"),
	phoneNumber: text("phone_number"),
	dateOfBirth: date("date_of_birth"),
	gender: gender(),
	role: userRole().default('dater').notNull(),
	pushToken: text("push_token"),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	unique("profiles_username_key").on(table.username),
	pgPolicy("Public profiles are viewable by everyone.", { as: "permissive", for: "select", to: ["public"], using: sql`true` }),
	pgPolicy("Users can insert their own profile.", { as: "permissive", for: "insert", to: ["public"] }),
	pgPolicy("Users can update their own profile.", { as: "permissive", for: "update", to: ["public"] }),
	check("username_length", sql`char_length(username) >= 3`),
]);

export const profilePhotos = pgTable("profile_photos", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	datingProfileId: uuid("dating_profile_id").notNull(),
	suggesterId: uuid("suggester_id"),
	storageUrl: text("storage_url").notNull(),
	displayOrder: integer("display_order").notNull(),
	approvedAt: timestamp("approved_at", { withTimezone: true, mode: 'string' }),
	rejectedAt: timestamp("rejected_at", { withTimezone: true, mode: 'string' }),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("profile_photos_dating_profile_id_display_order_idx").using("btree", table.datingProfileId.asc().nullsLast().op("int4_ops"), table.displayOrder.asc().nullsLast().op("int4_ops")),
	index("profile_photos_suggester_id_idx").using("btree", table.suggesterId.asc().nullsLast().op("uuid_ops")).where(sql`(suggester_id IS NOT NULL)`),
	foreignKey({
			columns: [table.datingProfileId],
			foreignColumns: [datingProfiles.id],
			name: "profile_photos_dating_profile_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.suggesterId],
			foreignColumns: [profiles.id],
			name: "profile_photos_suggester_id_fkey"
		}).onDelete("set null"),
	pgPolicy("Photos viewable when approved or own/suggested", { as: "permissive", for: "select", to: ["authenticated"], using: sql`(EXISTS ( SELECT 1
   FROM dating_profiles dp
  WHERE ((dp.id = profile_photos.dating_profile_id) AND ((dp.user_id = auth.uid()) OR (profile_photos.suggester_id = auth.uid()) OR ((dp.is_active = true) AND (profile_photos.approved_at IS NOT NULL))))))` }),
	pgPolicy("Users can insert photos for their own profile", { as: "permissive", for: "insert", to: ["authenticated"] }),
	pgPolicy("Users can update photos for their own profile", { as: "permissive", for: "update", to: ["authenticated"] }),
	pgPolicy("Users can delete photos for their own profile", { as: "permissive", for: "delete", to: ["authenticated"] }),
]);

export const promptTemplates = pgTable("prompt_templates", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	question: text().notNull(),
}, (table) => [
	pgPolicy("Prompt templates readable by authenticated users", { as: "permissive", for: "select", to: ["authenticated"], using: sql`true` }),
]);

export const profilePrompts = pgTable("profile_prompts", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	datingProfileId: uuid("dating_profile_id").notNull(),
	promptTemplateId: uuid("prompt_template_id").notNull(),
	answer: text().notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("profile_prompts_dating_profile_id_idx").using("btree", table.datingProfileId.asc().nullsLast().op("uuid_ops")),
	index("profile_prompts_prompt_template_id_idx").using("btree", table.promptTemplateId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.datingProfileId],
			foreignColumns: [datingProfiles.id],
			name: "profile_prompts_dating_profile_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.promptTemplateId],
			foreignColumns: [promptTemplates.id],
			name: "profile_prompts_prompt_template_id_fkey"
		}),
	pgPolicy("Profile prompts viewable when profile is active or own", { as: "permissive", for: "select", to: ["authenticated"], using: sql`(EXISTS ( SELECT 1
   FROM dating_profiles dp
  WHERE ((dp.id = profile_prompts.dating_profile_id) AND ((dp.is_active = true) OR (dp.user_id = auth.uid())))))` }),
	pgPolicy("Users can insert prompts for their own profile", { as: "permissive", for: "insert", to: ["authenticated"] }),
	pgPolicy("Users can update prompts for their own profile", { as: "permissive", for: "update", to: ["authenticated"] }),
	pgPolicy("Users can delete prompts for their own profile", { as: "permissive", for: "delete", to: ["authenticated"] }),
]);

export const promptResponses = pgTable("prompt_responses", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	userId: uuid("user_id").notNull(),
	profilePromptId: uuid("profile_prompt_id").notNull(),
	message: text().notNull(),
	isApproved: boolean("is_approved").default(false).notNull(),
	isRejected: boolean("is_rejected").default(false).notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("prompt_responses_profile_prompt_id_idx").using("btree", table.profilePromptId.asc().nullsLast().op("uuid_ops")),
	index("prompt_responses_user_id_idx").using("btree", table.userId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [profiles.id],
			name: "prompt_responses_user_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.profilePromptId],
			foreignColumns: [profilePrompts.id],
			name: "prompt_responses_profile_prompt_id_fkey"
		}).onDelete("cascade"),
	pgPolicy("Users can view relevant prompt responses", { as: "permissive", for: "select", to: ["authenticated"], using: sql`((user_id = auth.uid()) OR (EXISTS ( SELECT 1
   FROM (profile_prompts pp
     JOIN dating_profiles dp ON ((dp.id = pp.dating_profile_id)))
  WHERE ((pp.id = prompt_responses.profile_prompt_id) AND (dp.user_id = auth.uid())))))` }),
	pgPolicy("Authenticated users can send prompt responses", { as: "permissive", for: "insert", to: ["authenticated"] }),
	pgPolicy("Profile owners can update prompt responses", { as: "permissive", for: "update", to: ["authenticated"] }),
]);

export const contacts = pgTable("contacts", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	userId: uuid("user_id").notNull(),
	phoneNumber: text("phone_number").notNull(),
	wingerId: uuid("winger_id"),
	wingpersonStatus: wingpersonStatus("wingperson_status").default('invited').notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("contacts_user_id_idx").using("btree", table.userId.asc().nullsLast().op("uuid_ops")),
	index("contacts_winger_id_idx").using("btree", table.wingerId.asc().nullsLast().op("uuid_ops")).where(sql`(winger_id IS NOT NULL)`),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [profiles.id],
			name: "contacts_user_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.wingerId],
			foreignColumns: [profiles.id],
			name: "contacts_winger_id_fkey"
		}).onDelete("set null"),
	pgPolicy("Users can update contacts they are party to", { as: "permissive", for: "update", to: ["authenticated"], using: sql`((user_id = auth.uid()) OR (winger_id = auth.uid()))` }),
	pgPolicy("Users can view contacts they are party to", { as: "permissive", for: "select", to: ["authenticated"] }),
	pgPolicy("Users can insert their own contacts", { as: "permissive", for: "insert", to: ["authenticated"] }),
	pgPolicy("Users can delete their own contacts", { as: "permissive", for: "delete", to: ["authenticated"] }),
]);

export const decisions = pgTable("decisions", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	actorId: uuid("actor_id").notNull(),
	recipientId: uuid("recipient_id").notNull(),
	decision: decisionType(),
	suggestedBy: uuid("suggested_by"),
	note: text(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("decisions_actor_id_idx").using("btree", table.actorId.asc().nullsLast().op("uuid_ops")),
	index("decisions_recipient_id_idx").using("btree", table.recipientId.asc().nullsLast().op("uuid_ops")),
	index("decisions_suggested_by_idx").using("btree", table.suggestedBy.asc().nullsLast().op("uuid_ops")).where(sql`(suggested_by IS NOT NULL)`),
	foreignKey({
			columns: [table.actorId],
			foreignColumns: [profiles.id],
			name: "decisions_actor_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.recipientId],
			foreignColumns: [profiles.id],
			name: "decisions_recipient_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.suggestedBy],
			foreignColumns: [profiles.id],
			name: "decisions_suggested_by_fkey"
		}).onDelete("set null"),
	unique("unique_actor_recipient").on(table.actorId, table.recipientId),
	pgPolicy("Users can view decisions they are party to", { as: "permissive", for: "select", to: ["authenticated"], using: sql`((actor_id = auth.uid()) OR (recipient_id = auth.uid()) OR (suggested_by = auth.uid()))` }),
	pgPolicy("Users can insert decisions as actor or wingperson", { as: "permissive", for: "insert", to: ["authenticated"] }),
	pgPolicy("Actors can update their own decisions", { as: "permissive", for: "update", to: ["authenticated"] }),
	check("no_self_decision", sql`actor_id <> recipient_id`),
]);

export const matches = pgTable("matches", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	userAId: uuid("user_a_id").notNull(),
	userBId: uuid("user_b_id").notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("matches_user_a_id_idx").using("btree", table.userAId.asc().nullsLast().op("uuid_ops")),
	index("matches_user_b_id_idx").using("btree", table.userBId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.userAId],
			foreignColumns: [profiles.id],
			name: "matches_user_a_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.userBId],
			foreignColumns: [profiles.id],
			name: "matches_user_b_id_fkey"
		}).onDelete("cascade"),
	unique("unique_match").on(table.userAId, table.userBId),
	pgPolicy("Users can view their own matches", { as: "permissive", for: "select", to: ["authenticated"], using: sql`((user_a_id = auth.uid()) OR (user_b_id = auth.uid()))` }),
	check("ordered_match_ids", sql`user_a_id < user_b_id`),
]);

export const messages = pgTable("messages", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	matchId: uuid("match_id").notNull(),
	senderId: uuid("sender_id").notNull(),
	body: text().notNull(),
	isRead: boolean("is_read").default(false).notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
}, (table) => [
	index("messages_match_id_created_at_idx").using("btree", table.matchId.asc().nullsLast().op("timestamptz_ops"), table.createdAt.asc().nullsLast().op("timestamptz_ops")),
	index("messages_sender_id_idx").using("btree", table.senderId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.matchId],
			foreignColumns: [matches.id],
			name: "messages_match_id_fkey"
		}).onDelete("cascade"),
	foreignKey({
			columns: [table.senderId],
			foreignColumns: [profiles.id],
			name: "messages_sender_id_fkey"
		}).onDelete("cascade"),
	pgPolicy("Users can view messages in their matches", { as: "permissive", for: "select", to: ["authenticated"], using: sql`(EXISTS ( SELECT 1
   FROM matches m
  WHERE ((m.id = messages.match_id) AND ((m.user_a_id = auth.uid()) OR (m.user_b_id = auth.uid())))))` }),
	pgPolicy("Users can send messages in their matches", { as: "permissive", for: "insert", to: ["authenticated"] }),
	pgPolicy("Senders can mark their own messages read", { as: "permissive", for: "update", to: ["authenticated"] }),
]);

export const datingProfiles = pgTable("dating_profiles", {
	id: uuid().defaultRandom().primaryKey().notNull(),
	userId: uuid("user_id").notNull(),
	bio: text(),
	interestedGender: gender("interested_gender").array().notNull(),
	ageFrom: integer("age_from").notNull(),
	ageTo: integer("age_to"),
	religion: religion().notNull(),
	religiousPreference: religion("religious_preference"),
	interests: interest().array().notNull(),
	isActive: boolean("is_active").default(true).notNull(),
	datingStatus: datingStatus("dating_status").default('open').notNull(),
	createdAt: timestamp("created_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	updatedAt: timestamp("updated_at", { withTimezone: true, mode: 'string' }).defaultNow().notNull(),
	city: city().notNull(),
}, (table) => [
	index("dating_profiles_is_active_city_idx").using("btree", table.isActive.asc().nullsLast().op("bool_ops"), table.city.asc().nullsLast().op("enum_ops")),
	index("dating_profiles_user_id_idx").using("btree", table.userId.asc().nullsLast().op("uuid_ops")),
	foreignKey({
			columns: [table.userId],
			foreignColumns: [profiles.id],
			name: "dating_profiles_user_id_fkey"
		}).onDelete("cascade"),
	unique("dating_profiles_user_id_key").on(table.userId),
	pgPolicy("Active profiles viewable by authenticated users", { as: "permissive", for: "select", to: ["authenticated"], using: sql`((is_active = true) OR (user_id = auth.uid()))` }),
	pgPolicy("Users can insert their own dating profile", { as: "permissive", for: "insert", to: ["authenticated"] }),
	pgPolicy("Users can update their own dating profile", { as: "permissive", for: "update", to: ["authenticated"] }),
	pgPolicy("Users can delete their own dating profile", { as: "permissive", for: "delete", to: ["authenticated"] }),
]);
