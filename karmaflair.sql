--
-- Name: karma; Type: TABLE; Schema: public;
--

CREATE TABLE karma (
    id text NOT NULL,
    name text NOT NULL,
    granter text NOT NULL,
    type text NOT NULL,
    replied boolean DEFAULT false,
    session_id uuid NOT NULL
);

--
-- Name: karma_pkey; Type: CONSTRAINT; Schema: public;
--

ALTER TABLE ONLY karma
    ADD CONSTRAINT karma_pkey PRIMARY KEY (id, name, granter, type);
