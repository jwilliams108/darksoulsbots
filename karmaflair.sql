--
-- PostgreSQL database dump
--

SET statement_timeout = 0;
SET lock_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SET check_function_bodies = false;
SET client_min_messages = warning;

--
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET search_path = public, pg_catalog;

SET default_tablespace = '';

SET default_with_oids = false;

--
-- Name: karma; Type: TABLE; Schema: public; Owner: karmaflair; Tablespace: 
--

CREATE TABLE karma (
    id text NOT NULL,
    name text NOT NULL,
    granter text NOT NULL
);


ALTER TABLE karma OWNER TO karmaflair;

--
-- Name: id_name_granter; Type: CONSTRAINT; Schema: public; Owner: karmaflair; Tablespace: 
--

ALTER TABLE ONLY karma
    ADD CONSTRAINT id_name_granter PRIMARY KEY (id, name, granter);


--
-- Name: public; Type: ACL; Schema: -; Owner: karmaflair
--

REVOKE ALL ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM karmaflair;
GRANT ALL ON SCHEMA public TO karmaflair;
GRANT ALL ON SCHEMA public TO PUBLIC;


--
-- PostgreSQL database dump complete
--

